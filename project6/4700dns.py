#!/usr/bin/env -S python3 -u
import argparse, socket, time, select, sys, threading, copy
from dnslib import DNSRecord, DNSHeader, RR, QTYPE, RCODE, CLASS
from dnslib.dns import DNSQuestion

DNS_PORT = 60053
TIMEOUT  = 2    # seconds per query attempt
RETRIES  = 3    # max attempts per server

def log(msg):
    sys.stderr.write(msg + "\n")
    sys.stderr.flush()

#  cache
#  Fix: 18-cache.conf — TTL-respecting cache so repeated queries
#  within the TTL window return consistent cached results
class Cache:
    def __init__(self):
        self._lock  = threading.Lock()
        self._store = {}   # (name_lower, qtype_int) -> [(rr, expire_time)]

    def _key(self, name, qtype):
        return (str(name).rstrip('.').lower(), int(qtype))

    def put(self, rr, now=None):
        """Cache one RR. TTL=0 records are never cached."""
        if rr.ttl <= 0:
            return
        now    = now or time.time()
        k      = self._key(rr.rname, rr.rtype)
        expire = now + rr.ttl
        with self._lock:
            bucket = self._store.setdefault(k, [])
            strs   = {str(e[0]) for e in bucket}
            if str(rr) not in strs:
                bucket.append((rr, expire))

    def put_many(self, rrs, now=None):
        now = now or time.time()
        for rr in rrs:
            self.put(rr, now)

    def get(self, name, qtype, now=None):
        """Return live RRs with adjusted TTLs, or None on miss/expiry."""
        now = now or time.time()
        k   = self._key(name, qtype)
        with self._lock:
            bucket = self._store.get(k)
            if not bucket:
                return None
            live = [(rr, exp) for rr, exp in bucket if exp > now]
            self._store[k] = live
            if not live:
                return None
            result = []
            for rr, exp in live:
                c     = copy.copy(rr)
                c.ttl = max(1, int(exp - now))
                result.append(c)
            return result

    def evict(self):
        """Periodically purge fully-expired cache buckets."""
        now = time.time()
        with self._lock:
            for k in list(self._store):
                live = [(rr, e) for rr, e in self._store[k] if e > now]
                if live:
                    self._store[k] = live
                else:
                    del self._store[k]

#  Bailiwick helpers
#  Fix: 17-bailiwick.conf — only cache/trust records whose owner
#  name falls within the responding server's zone
def in_bailiwick(record_name, server_zone):
    rn = str(record_name).rstrip('.').lower()
    sz = str(server_zone).rstrip('.').lower()
    if sz in ('', '.'):
        return True   # root serves everything
    return rn == sz or rn.endswith('.' + sz)

def filter_bailiwick(rrs, zone):
    """Keep only RRs whose owner is at or under zone."""
    return [r for r in rrs if in_bailiwick(r.rname, zone)]

def is_valid_answer(rr, qname):
    """
    Fix: 17-bailiwick.conf — reject answer records whose owner
    name doesn't match the queried name. e.g. a server for
    bailiwick.foo must not inject answers for bailiwick.bar.
    CNAME records are always accepted (they form chain links).
    """
    rname = str(rr.rname).rstrip('.').lower()
    qn    = qname.rstrip('.').lower()
    if rr.rtype == QTYPE.CNAME:
        return True
    return rname == qn

#  Zone loading
#  Used by: 1-local-a.conf, 2-local-cname-mx.conf,
#           3-local-ns-txt.conf, 4-local-nxdomain.conf
#  Parses the BIND-style zone file and builds a lookup index.
def load_zone(path):
    with open(path) as f:
        text = f.read()
    rrs    = list(RR.fromZone(text))
    origin = None
    for rr in rrs:
        if rr.rtype == QTYPE.SOA:
            origin = str(rr.rname).rstrip('.')
            break
    if origin is None:
        for line in text.splitlines():
            s = line.strip()
            if s.upper().startswith('$ORIGIN'):
                origin = s.split()[1].rstrip('.')
                break
    return origin, rrs

def build_index(rrs):
    idx = {}
    for rr in rrs:
        k = (str(rr.rname).rstrip('.').lower(), int(rr.rtype))
        idx.setdefault(k, []).append(rr)
    return idx

def zlookup(idx, name, qtype):
    return idx.get((str(name).rstrip('.').lower(), int(qtype)), [])

def zhas(idx, name):
    n = str(name).rstrip('.').lower()
    return any(k[0] == n for k in idx)

#  UDP query helpers
#  Fix: 20-drop.conf / 11-sub-ns.conf (trunc) —
#
#  send_and_recv uses a SHARED socket passed in from the caller.
#  Reusing the same socket across retries is critical because the
#  erratic plugin (drop 2 / truncate 2) counts packets per
#  connection. A fresh socket resets that counter, meaning every
#  attempt lands on the "bad" slot. Sharing the socket advances
#  the counter so attempt 2 hits the "good" slot.
#
#  query_server retries on timeout (drop) and TC (trunc) but
#  returns immediately on SERVFAIL/NXDOMAIN.
def send_and_recv(sock, ip, qname, qtype, timeout=TIMEOUT):
    """
    Send one DNS query on an existing socket and wait for a reply.
    Each call generates a new query ID to avoid cross-thread confusion.
    Returns (DNSRecord, tc_bool) or (None, False) on timeout.
    """
    try:
        qtype_str   = QTYPE[qtype] if isinstance(qtype, int) else qtype
        # Fix: 10-root-ns.conf — preserve "." for root zone queries.
        label       = qname if qname else "."
        q           = DNSRecord.question(label, qtype_str)
        q.header.rd = 0   # we are the resolver; don't ask upstreams to recurse
        sock.sendto(q.pack(), (ip, DNS_PORT))
        deadline = time.time() + timeout
        while True:
            rem = deadline - time.time()
            if rem <= 0:
                return None, False
            r, _, _ = select.select([sock], [], [], rem)
            if not r:
                return None, False
            try:
                data, addr = sock.recvfrom(65535)
                pkt = DNSRecord.parse(data)
            except Exception:
                continue
            if pkt.header.id == q.header.id:
                return pkt, bool(pkt.header.tc)
    except Exception as e:
        log("  send_and_recv error: %s" % e)
        return None, False

def query_server(sock, ip, qname, qtype, retries=RETRIES, timeout=TIMEOUT):
    """
    Retry on timeout (20-drop.conf) or TC (11-sub-ns.conf trunc).
    Return immediately on any complete response (even SERVFAIL).
    Socket is shared across retries so erratic counters advance.
    """
    for attempt in range(retries):
        resp, tc = send_and_recv(sock, ip, qname, qtype, timeout)
        if resp is None:
            log("  timeout attempt %d/%d %s @ %s" % (attempt+1, retries, qname, ip))
            continue
        if tc:
            log("  TC attempt %d/%d %s @ %s" % (attempt+1, retries, qname, ip))
            continue
        return resp
    return None

# recrusive resolver
class Resolver:
    def __init__(self, root_ip, cache):
        self.root_ip = root_ip
        self.cache   = cache

    def resolve(self, qname, qtype, depth=0):
        """
        Public entry point. Creates one socket per resolution chain
        so erratic counters advance across retries (20-drop.conf fix).
        Recursive sub-resolutions (CNAME targets, NS addresses) each
        get their own fresh socket since they are independent chains.
        """
        if depth > 20:
            return None

        # Fix: 18-cache.conf — serve from cache before hitting the wire
        cached = self.cache.get(qname, qtype)
        if cached:
            log("  cache hit: %s %s" % (qname, QTYPE[qtype]))
            return self._answer(qname, qtype, RCODE.NOERROR, cached)

        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            return self._resolve_with_sock(sock, qname, qtype, depth)
        finally:
            sock.close()

    def _resolve_with_sock(self, sock, qname, qtype, depth):
        """
        Iterative resolution starting from root, walking referrals.
        Tracks last_referral so we can fall back gracefully when the
        authoritative server is broken (11-sub-ns.conf trunc SERVFAIL fix).
        """
        ns_ip         = self.root_ip
        zone          = "."
        # Fix: 11-sub-ns.conf — trunc server returns SERVFAIL on its NS query.
        # The root already gave us the NS referral (trunc NS ns.trunc + glue),
        # so we save it here and return it when the auth server fails.
        last_referral = None

        for _ in range(40):
            log("  [resolve] %s %s @ %s (zone=%s)" % (
                qname, QTYPE[qtype], ns_ip, zone))
            resp = query_server(sock, ns_ip, qname, qtype)

            # All retries failed (timeout/TC) — return best referral we have
            if resp is None:
                log("  failed from %s — using last referral" % ns_ip)
                return last_referral

            rcode = resp.header.rcode

            # Fix: 17-bailiwick.conf — only cache records within the
            # responding server's zone (bailiwick). Discards injected
            # out-of-zone records before they pollute the cache.
            safe = filter_bailiwick(
                list(resp.rr) + list(resp.auth) + list(resp.ar), zone)
            self.cache.put_many(safe)

            if rcode == RCODE.NXDOMAIN:
                return resp

            # Fix: 11-sub-ns.conf — trunc server returns SERVFAIL instead
            # of TC or timeout. Fall back to last referral (the root's
            # referral has the NS + glue the client needs).
            if rcode == RCODE.SERVFAIL:
                log("  SERVFAIL from %s — using last referral" % ns_ip)
                return last_referral

            if rcode != RCODE.NOERROR:
                return resp

            # ---- Answer section ----
            if resp.rr:
                # Fix: 17-bailiwick.conf — strip answer records whose owner
                # doesn't match qname. Prevents cross-domain answer injection
                # (e.g. bailiwick.foo server answering with bailiwick.bar records).
                valid_answers = [r for r in resp.rr if is_valid_answer(r, qname)]

                if not valid_answers:
                    # All answers were bogus injections — return empty NOERROR
                    return self._answer(qname, qtype, RCODE.NOERROR, [])

                ans_typed = [r for r in valid_answers if r.rtype == qtype]
                cnames    = [r for r in valid_answers if r.rtype == QTYPE.CNAME]

                if ans_typed:
                    # Direct answer — build clean response with filtered additional
                    out = DNSRecord(DNSHeader(rcode=RCODE.NOERROR))
                    out.add_question(DNSQuestion(qname, qtype))
                    for r in valid_answers: out.add_answer(r)
                    for r in resp.auth:     out.add_auth(r)
                    # Fix: 17-bailiwick.conf — filter additional by zone bailiwick
                    for r in resp.ar:
                        if in_bailiwick(r.rname, zone):
                            out.add_ar(r)
                    return out

                if cnames and qtype != QTYPE.CNAME:
                    # Follow CNAME chain — resolve the target independently
                    target   = str(cnames[-1].rdata).rstrip('.')
                    cached_t = self.cache.get(target, qtype)
                    if cached_t:
                        out = self._answer(qname, qtype, RCODE.NOERROR, [])
                        for r in cnames:   out.add_answer(r)
                        for r in cached_t: out.add_answer(r)
                        return out
                    sub = self.resolve(target, qtype, depth + 1)
                    if sub is None:
                        out = self._answer(qname, qtype, RCODE.NOERROR, [])
                        for r in cnames: out.add_answer(r)
                        return out
                    out = self._answer(qname, qtype, RCODE.NOERROR, [])
                    for r in cnames:  out.add_answer(r)
                    for r in sub.rr:  out.add_answer(r)
                    return out

                return self._answer(qname, qtype, RCODE.NOERROR, [])

            # ---- Referral ----
            ns_rrs = [r for r in list(resp.auth) + list(resp.rr)
                      if r.rtype == QTYPE.NS]
            if not ns_rrs:
                return self._answer(qname, qtype, RCODE.NOERROR, [])

            # Pick the most specific NS record that is still relevant to qname
            best, best_len = ns_rrs[0], -1
            for nr in ns_rrs:
                z = str(nr.rname).rstrip('.')
                if in_bailiwick(qname, z) and len(z) > best_len:
                    best, best_len = nr, len(z)

            zone    = str(best.rname).rstrip('.')
            ns_name = str(best.rdata).rstrip('.')

            # Save referral BEFORE moving to next server so we can fall back
            # if the next server is broken (11-sub-ns.conf trunc fix)
            last_referral = resp

            # Glue A record provided in additional?
            glue = [r for r in resp.ar
                    if r.rtype == QTYPE.A and
                    str(r.rname).rstrip('.').lower() == ns_name.lower()]
            if glue:
                ns_ip = str(glue[0].rdata)
                continue

            # Fix: 18-cache.conf — check cache for NS server address
            # before going back to the wire
            ca = self.cache.get(ns_name, QTYPE.A)
            if ca:
                ns_ip = str(ca[0].rdata)
                continue

            # Need to resolve NS address — use a fresh socket (independent chain)
            sub = self.resolve(ns_name, QTYPE.A, depth + 1)
            if not sub or not sub.rr:
                return None
            a_rrs = [r for r in sub.rr if r.rtype == QTYPE.A]
            if not a_rrs:
                return None
            ns_ip = str(a_rrs[0].rdata)

        return None

    def _answer(self, qname, qtype, rcode, rrs):
        r = DNSRecord(DNSHeader(rcode=rcode))
        r.add_question(DNSQuestion(qname, qtype))
        for rr in rrs:
            r.add_answer(rr)
        return r

#server impl
class Server:
    def __init__(self, root_ip, zone_file, port=0):
        self.root_ip          = root_ip
        self.origin, zone_rrs = load_zone(zone_file)
        self.zone_rrs         = zone_rrs
        self.zone_idx         = build_index(zone_rrs)
        log("Authoritative for: %s" % self.origin)

        self.cache    = Cache()
        self.resolver = Resolver(root_ip, self.cache)

        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind(("127.0.0.1", port))
        self.port = self.sock.getsockname()[1]
        print("Bound to port %d" % self.port)
        sys.stdout.flush()
        log("Bound to port %d" % self.port)

    def run(self):
        last_evict = time.time()
        while True:
            ready, _, _ = select.select([self.sock], [], [], 1.0)
            for s in ready:
                try:
                    data, addr = s.recvfrom(65535)
                except Exception:
                    continue
                # each client request handled in its own thread so slow (14-sub-a.conf fix)
                threading.Thread(target=self._handle,
                                 args=(data, addr), daemon=True).start()
            if time.time() - last_evict > 30:
                self.cache.evict()
                last_evict = time.time()

    def _handle(self, data, addr):
        try:
            req = DNSRecord.parse(data)
        except Exception as e:
            log("Bad packet from %s: %s" % (addr, e))
            return

        # Spec requires SERVFAIL for multi-question packets
        if len(req.questions) != 1:
            r = req.reply()
            r.header.rcode = RCODE.SERVFAIL
            self._send(addr, r)
            return

        q     = req.questions[0]
        raw   = str(q.qname)
        # Fix: 10-root-ns.conf — "." strips to "" which breaks lookups;
        # preserve it for root-zone queries
        qname = raw if raw == '.' else raw.rstrip('.')
        qtype = int(q.qtype)
        log("[%s:%d] %s %s" % (addr[0], addr[1], qname,
            QTYPE[qtype] if qtype in QTYPE.reverse else str(qtype)))

        if self._is_auth(qname):
            resp = self._auth_response(req, qname, qtype)
        else:
            # spec: if RD flag not set, return SERVFAIL (no recursive service)
            if not req.header.rd:
                resp = req.reply()
                resp.header.rcode = RCODE.SERVFAIL
            else:
                resp = self._recursive_response(req, qname, qtype)

        self._send(addr, resp)

    def _is_auth(self, qname):
        qn = qname.rstrip('.').lower()
        o  = self.origin.rstrip('.').lower()
        return qn == o or qn.endswith('.' + o)

    def _add_ns_authority(self, resp):
        """
        helper to fix: 1-local-a.conf — simulator compares against reference server
        which always includes NS records in the AUTHORITY section for
        authoritative responses. Add them here for every auth response.
        """
        for ns in zlookup(self.zone_idx, self.origin, QTYPE.NS):
            resp.add_auth(ns)

    def _auth_response(self, req, qname, qtype):
        """
        Serves records from our zone file authoritatively.
        Covers: 1-local-a.conf (A), 2-local-cname-mx.conf (CNAME/MX),
                3-local-ns-txt.conf (NS/TXT), 4-local-nxdomain.conf (NXDOMAIN)
        """
        resp = req.reply()
        resp.header.aa = 1   # Authoritative Answer
        # Fix: 1-local-a.conf — reference server always sets RA=1;
        # simulator failed because our flag was 0
        resp.header.ra = 1

        # any query ; return all records for this name
        if qtype == QTYPE.ANY:
            n = qname.rstrip('.').lower()
            for rr in self.zone_rrs:
                if str(rr.rname).rstrip('.').lower() == n:
                    resp.add_answer(rr)
            self._add_ns_authority(resp)
            return resp

        # Explicit CNAME query — return the CNAME record directly
        if qtype == QTYPE.CNAME:
            for rr in zlookup(self.zone_idx, qname, QTYPE.CNAME):
                resp.add_answer(rr)
            self._add_ns_authority(resp)
            return resp

        # For non-CNAME queries, follow any CNAME chain first
        # Fix: 2-local-cname-mx.conf — mail/www CNAMEs must be resolved
        chain, cur, seen = [], qname, set()
        while True:
            lc = cur.lower()
            if lc in seen:
                break
            seen.add(lc)
            cn = zlookup(self.zone_idx, cur, QTYPE.CNAME)
            if not cn:
                break
            chain.append(cn[0])
            cur = str(cn[0].rdata).rstrip('.')

        if chain:
            for rr in chain:
                resp.add_answer(rr)
            final = str(chain[-1].rdata).rstrip('.')
            if self._is_auth(final):
                for rr in zlookup(self.zone_idx, final, qtype):
                    resp.add_answer(rr)
            self._add_ns_authority(resp)
            return resp

        direct = zlookup(self.zone_idx, qname, qtype) #direct record lookup
        if direct:
            for rr in direct:
                resp.add_answer(rr)
            if qtype == QTYPE.NS:
                # Fix: 3-local-ns-txt.conf — NS queries need glue A records
                # in ADDITIONAL; NS records go in ANSWER not AUTHORITY
                for nr in direct:
                    ns_name = str(nr.rdata).rstrip('.')
                    for g in zlookup(self.zone_idx, ns_name, QTYPE.A):
                        resp.add_ar(g)
            elif qtype == QTYPE.MX:
                # Fix: 2-local-cname-mx.conf — MX queries need A records
                # for the mail exchange in ADDITIONAL
                for mr in direct:
                    try:
                        mx_name = str(mr.rdata.label).rstrip('.')
                    except Exception:
                        continue
                    if self._is_auth(mx_name):
                        for a in zlookup(self.zone_idx, mx_name, QTYPE.A):
                            resp.add_ar(a)
            # NS queries have their records in ANSWER already; skip authority
            if qtype != QTYPE.NS:
                self._add_ns_authority(resp)
            return resp

        # name exists but no record of this type → NOERROR empty answer
        if zhas(self.zone_idx, qname):
            self._add_ns_authority(resp)
            return resp

        # fix: 4-local-nxdomain.conf — name not found → NXDOMAIN + SOA
        resp.header.rcode = RCODE.NXDOMAIN
        for soa in zlookup(self.zone_idx, self.origin, QTYPE.SOA):
            resp.add_auth(soa)
        return resp

    def _recursive_response(self, req, qname, qtype):
        """
        Wraps resolver result into a client response.
        Covers: 10-root-ns.conf through 21-delay.conf
        """
        resp = req.reply()
        resp.header.aa = 0   # not authoritative — we resolved recursively
        resp.header.ra = 1   # recursion available

        result = self.resolver.resolve(qname, qtype)
        if result is None:
            resp.header.rcode = RCODE.SERVFAIL
            return resp

        resp.header.rcode = result.header.rcode
        for rr in result.rr:   resp.add_answer(rr)
        for rr in result.auth: resp.add_auth(rr)

        # fix: 17-bailiwick.conf — only pass through additional records
        # whose owner name was actually mentioned in answer or authority.
        mentioned = set()
        for rr in list(result.rr) + list(result.auth):
            mentioned.add(str(rr.rname).rstrip('.').lower())
            if rr.rtype == QTYPE.NS:
                mentioned.add(str(rr.rdata).rstrip('.').lower())
            elif rr.rtype == QTYPE.MX:
                try:
                    mentioned.add(str(rr.rdata.label).rstrip('.').lower())
                except Exception:
                    pass

        for rr in result.ar:
            rn = str(rr.rname).rstrip('.').lower()
            if rn in mentioned:
                resp.add_ar(rr)

        # fix: 10-root-ns.conf — when serving a pure NS referral from cache,
        # the cached entry "had"n o glue
        if not list(result.rr) and not list(result.ar):
            for rr in list(result.auth):
                if rr.rtype == QTYPE.NS:
                    ns_name  = str(rr.rdata).rstrip('.')
                    cached_a = self.cache.get(ns_name, QTYPE.A)
                    if cached_a:
                        for a in cached_a:
                            resp.add_ar(a)

        return resp

    def _send(self, addr, msg):
        try:
            self.sock.sendto(msg.pack(), addr)
        except Exception as e:
            log("Send error to %s: %s" % (addr, e))

#  main
#  sim  launches as: ./4700dns root zone
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='4700dns')
    parser.add_argument('root_ip', type=str)
    parser.add_argument('zone',    type=str)
    parser.add_argument('--port',  type=int, default=0)
    args = parser.parse_args()
    Server(args.root_ip, args.zone, args.port).run()

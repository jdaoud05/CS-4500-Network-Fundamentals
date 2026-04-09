Challenges:
- the crawler was visiting /accounts/logout/ mid-crawl, logging itself out and draining the frontier. fixed by ignoring any link that didn't start with /fakebook/.
- chunked transfer encoding was never properly reassembled in my original implementation, causing raw hex chunk headers to be passed to the HTML parser and breaking scraping entirely.

Testing:
- tested against fakebook.khoury.northeastern.edu with stderr debug prints tracking cookie values, status codes, and visited/frontier counts to confirm login success and forward progress.
// NOTE:
// The starter code uses a simple JSON encoder for message serialization and deserialization. 
// You must replace this with a JSON library of your choice, such as: Gson, org.json, Jackson

// Ensure that your chosen library correctly encodes and decodes messages while maintaining 
// the expected structure required by the simulator.

import java.io.IOException;
import java.net.*;
import java.nio.ByteBuffer;
import java.nio.channels.*;
import java.util.*;

public class Router {
    private final int asn;
    private final Map<String, String> relations = new HashMap<>();
    private final Map<String, DatagramChannel> channels = new HashMap<>();
    private final Map<String, Integer> ports = new HashMap<>();
    private final Selector selector;
    private final DatagramChannel serverChannel;
    private final Map<Integer, String> portToIpMap; 

    public Router(int asn, List<String> connections) throws IOException {
        System.out.println("Router at AS " + asn + " starting up");
        this.asn = asn;
        this.selector = Selector.open();
        this.portToIpMap = new HashMap<>(); // Initialize port-to-IP mapping

        this.serverChannel = DatagramChannel.open();
        serverChannel.configureBlocking(false);
        serverChannel.socket().bind(new InetSocketAddress(0));
        serverChannel.register(selector, SelectionKey.OP_READ);

        int assignedPort = serverChannel.socket().getLocalPort();

        for (String relationship : connections) {
            String[] parts = relationship.split("-");
            if (parts.length >= 2) {
                int port = Integer.parseInt(parts[0]);
                String neighbor = parts[1];
                String relation = parts[2];

                portToIpMap.put(port, neighbor); // Store port-to-IP mapping
                channels.put(neighbor, serverChannel);
                ports.put(neighbor, port);
                relations.put(neighbor, relation);

                String handshakeMessage = createJsonMessage("handshake", ourAddr(neighbor), neighbor, "{}");
                send(neighbor, handshakeMessage);
            }
        }

    }

    private String ourAddr(String dst) {
        String[] quads = dst.split("\\.");
        quads[3] = "1";
        return String.join(".", quads);
    }

    private void send(String network, String message) throws IOException {
        DatagramChannel channel = channels.get(network);
        InetSocketAddress address = new InetSocketAddress("localhost", ports.get(network));
        ByteBuffer buffer = ByteBuffer.wrap(message.getBytes());
        channel.send(buffer, address);
    }

    private String createJsonMessage(String type, String src, String dst, String msg) {
        return String.format("{\"type\":\"%s\",\"src\":\"%s\",\"dst\":\"%s\",\"msg\":%s}", type, src, dst, msg);
    }

    public void run() throws IOException {
        ByteBuffer buffer = ByteBuffer.allocate(65535);

        while (true) {
            int readyChannels = selector.select();
            if (readyChannels == 0) {
                continue;
            }

            Iterator<SelectionKey> keyIterator = selector.selectedKeys().iterator();
            while (keyIterator.hasNext()) {
                SelectionKey key = keyIterator.next();
                keyIterator.remove();

                if (key.isReadable()) {
                    DatagramChannel channel = (DatagramChannel) key.channel();
                    buffer.clear();
                    SocketAddress senderAddress = channel.receive(buffer);

                    if (senderAddress != null) {
                        buffer.flip();
                        byte[] receivedData = new byte[buffer.remaining()];
                        buffer.get(receivedData);
                        String message = new String(receivedData);

                        InetSocketAddress inetSender = (InetSocketAddress) senderAddress;
                        int sourcePort = inetSender.getPort();
                        String senderIP = portToIpMap.getOrDefault(sourcePort, "Unknown");

                        System.out.println("Received message '" + message + "' from " + senderIP);
                    }
                }
            }
        }
    }

    public static void main(String[] args) {
        if (args.length < 2) {
            System.err.println("Usage: java Router <asn> <connections>");
            System.exit(1);
        }

        try {
            int asn = Integer.parseInt(args[0]);
            List<String> connections = Arrays.asList(Arrays.copyOfRange(args, 1, args.length));
            Router router = new Router(asn, connections);
            router.run();
        } catch (Exception e) {
            e.printStackTrace();
        }
    }
}

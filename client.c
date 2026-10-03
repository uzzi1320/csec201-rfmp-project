/*
 * client.c  -  RFMP unsecured C client (Person D)
 *
 * Flow: connect -> SS -> CC -> CM,openRead,<file> -> DP.../SC or EE -> End
 * Packets are plain text, comma-separated, UTF-8, ending with '\n'.
 *
 * Build (Linux/macOS):   gcc -Wall -o client client.c
 * Build (Windows MinGW): gcc -Wall -o client.exe client.c -lws2_32
 * Run: ./client [host] [port] [filename]
 */

#include <stdio.h>      // printf, fprintf, snprintf
#include <stdlib.h>     // atoi (text -> number)
#include <string.h>     // strlen, strcmp, strncmp, strchr, memset

#ifdef _WIN32                       // Windows needs winsock instead of the Unix socket headers
  #include <winsock2.h>
  #include <ws2tcpip.h>
  typedef SOCKET sock_t;            // socket type on Windows
  #define CLOSESOCK closesocket     // Windows closes sockets with closesocket()
#else
  #include <unistd.h>               // close()
  #include <sys/socket.h>           // socket, connect, send, recv
  #include <netinet/in.h>           // sockaddr_in, htons
  #include <arpa/inet.h>            // inet_pton (text IP -> binary IP)
  typedef int sock_t;               // socket type on Linux/macOS is a plain int
  #define CLOSESOCK close
  #define INVALID_SOCKET (-1)       // value returned when socket() fails
#endif

#define DEFAULT_HOST "127.0.0.1"    // server on this same laptop
#define DEFAULT_PORT 5000           // TODO: confirm port with Person A
#define DEFAULT_FILE "data.txt"     // file to ask the server to read
#define LINE_MAX_LEN 8192           // biggest packet we can hold in memory

/* Send the whole string; send() may write fewer bytes than we asked for. */
static int send_all(sock_t s, const char *msg)
{
    size_t total = 0;                        // bytes sent so far
    size_t len = strlen(msg);                // bytes we need to send
    while (total < len) {                    // keep going until everything is sent
        int n = send(s, msg + total, (int)(len - total), 0);  // send the remaining part
        if (n <= 0) return -1;               // error or connection closed
        total += (size_t)n;                  // move forward by what was actually sent
    }
    return 0;                                // success
}

/*
 * TCP is a stream, not separate messages, so one recv() could return half a
 * packet or two packets. We read 1 byte at a time until '\n' (end of packet).
 * Returns packet length (without '\n') or -1 if the connection closed.
 */
static int recv_packet(sock_t s, char *buf, size_t cap)
{
    size_t i = 0;                            // how many characters stored so far
    char c;                                  // one received character
    while (i < cap - 1) {                    // leave room for the final '\0'
        int n = recv(s, &c, 1, 0);           // read exactly one byte
        if (n <= 0) return -1;               // server closed or error
        if (c == '\n') break;                // '\n' marks the end of the packet
        buf[i++] = c;                        // store the character
    }
    buf[i] = '\0';                           // end the C string
    return (int)i;                           // number of characters in the packet
}

/*
 * Decode base64 text into raw bytes. The server base64-encodes the file
 * content so commas/newlines in the file can't break the packet format.
 * Base64 uses 64 symbols (A-Z a-z 0-9 + /), each worth 6 bits; every 4
 * symbols give back 3 original bytes. '=' at the end is just padding.
 * Returns number of decoded bytes written to out.
 */
static size_t b64_decode(const char *in, unsigned char *out)
{
    const char *table = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
    size_t o = 0;                            // bytes written to out so far
    unsigned int buf = 0;                    // holds bits waiting to become bytes
    int bits = 0;                            // how many valid bits are in buf
    for (const char *p = in; *p && *p != '='; p++) {   // stop at end or padding
        const char *pos = strchr(table, *p); // find this symbol's 6-bit value
        if (!pos) continue;                  // skip anything that isn't base64
        buf = (buf << 6) | (unsigned int)(pos - table);  // add 6 new bits
        bits += 6;
        if (bits >= 8) {                     // we have a full byte
            bits -= 8;
            out[o++] = (unsigned char)((buf >> bits) & 0xFF);  // take the top 8 bits
        }
    }
    return o;                                // length of decoded data
}

int main(int argc, char *argv[])
{
    const char *host = (argc > 1) ? argv[1] : DEFAULT_HOST;      // IP from args or default
    int port         = (argc > 2) ? atoi(argv[2]) : DEFAULT_PORT; // port from args or default
    const char *file = (argc > 3) ? argv[3] : DEFAULT_FILE;      // file name from args or default
    char line[LINE_MAX_LEN];                 // holds packets we receive
    char out[LINE_MAX_LEN];                  // holds packets we build to send

#ifdef _WIN32
    WSADATA wsa;                             // Windows-only: start the socket library
    if (WSAStartup(MAKEWORD(2, 2), &wsa) != 0) {
        fprintf(stderr, "WSAStartup failed\n");
        return 1;
    }
#endif

    /* ---------- connect to the server ---------- */
    sock_t sock = socket(AF_INET, SOCK_STREAM, 0);   // create a TCP socket (IPv4)
    if (sock == INVALID_SOCKET) { perror("socket"); return 1; }  // stop if it failed

    struct sockaddr_in addr;                 // server address structure
    memset(&addr, 0, sizeof(addr));          // zero it so no garbage values
    addr.sin_family = AF_INET;               // IPv4
    addr.sin_port = htons((unsigned short)port);  // port in network byte order
    if (inet_pton(AF_INET, host, &addr.sin_addr) != 1) {  // convert "127.0.0.1" to binary
        fprintf(stderr, "Bad IP address: %s\n", host);
        return 1;
    }
    if (connect(sock, (struct sockaddr *)&addr, sizeof(addr)) < 0) {  // open the connection
        perror("connect");                   // server not running / wrong port
        return 1;
    }
    printf("[C client] Connected to %s:%d\n", host, port);

    /* ---------- setup phase ---------- */
    if (send_all(sock, "SS,RFMP,v1.0,0\n") < 0) {    // Start-Packet, 0 = no encryption
        fprintf(stderr, "send failed\n");
        return 1;
    }
    printf("[C client] Sent Start-Packet: SS,RFMP,v1.0,0\n");

    if (recv_packet(sock, line, sizeof(line)) < 0) { // wait for the server's answer
        fprintf(stderr, "Server closed connection during setup\n");
        return 1;
    }
    if (strcmp(line, "CC") != 0) {           // must be exactly CC (Confirm-Connection)
        fprintf(stderr, "Expected CC, got: %s\n", line);
        return 1;
    }
    printf("[C client] Got Confirm-Connection-Packet (CC)\n");

    /* ---------- operation phase: openRead ---------- */
    snprintf(out, sizeof(out), "CM,openRead,%s\n", file);  // build CM,openRead,<file>\n
    if (send_all(sock, out) < 0) {           // send the command packet
        fprintf(stderr, "send failed\n");
        return 1;
    }
    printf("[C client] Sent: CM,openRead,%s\n", file);

    printf("----- file contents -----\n");
    int got_error = 0;                       // remember if the server reported an error
    while (recv_packet(sock, line, sizeof(line)) >= 0) {   // read reply packets one by one
        if (strncmp(line, "DP,", 3) == 0) {  // Data Packet: DP,<base64 file content>
            static unsigned char decoded[LINE_MAX_LEN];   // room for the decoded bytes
            size_t n = b64_decode(line + 3, decoded);     // decode the field after "DP,"
            fwrite(decoded, 1, n, stdout);   // print the real file content (may have newlines)
            printf("\n");
        } else if (strcmp(line, "SC") == 0 || strncmp(line, "SC,", 3) == 0) {  // success
            printf("----- end (server: success) -----\n");
            break;                           // server is done sending
        } else if (strncmp(line, "EE,", 3) == 0) {  // Exception Event: EE,<code>,<description>
            char *code = line + 3;           // error code starts after "EE,"
            char *desc = strchr(code, ',');  // find the comma between code and description
            if (desc) { *desc = '\0'; desc++; } else { desc = ""; }  // split into two strings
            fprintf(stderr, "[C client] Server error %s: %s\n", code, desc);
            got_error = 1;
            break;                           // stop reading after an error
        } else {                             // anything else is not in our protocol
            fprintf(stderr, "[C client] Unexpected packet: %s\n", line);
            got_error = 1;
            break;
        }
    }

    /* ---------- closing phase ---------- */
    send_all(sock, "End\n");                 // tell the server we're finished
    printf("[C client] Sent Close-Packet: End\n");

    CLOSESOCK(sock);                         // close the connection
#ifdef _WIN32
    WSACleanup();                            // Windows-only: shut down the socket library
#endif
    return got_error ? 1 : 0;                // exit code 0 = ok, 1 = error
}

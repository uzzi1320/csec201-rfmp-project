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

int main(void)
{
    return 0;
}


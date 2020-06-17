#ifndef __SIM_SOCKET_H
#define __SIM_SOCKET_H

#ifdef __cplusplus
extern "C" {
#endif

int socket_open(int port);
int socket_accept(int fd);
int socket_shutdown(int fd);
int socket_putchar(int fd, int c);
int socket_getchar(int fd);

#ifdef __cplusplus
}
#endif

#endif

#ifndef __SIM_DMI_H
#define __SIM_DMI_H

#ifdef __cplusplus
extern "C" {
#endif

int vpidmi_request(int fd, int *addr, int *data, int *op);
int vpidmi_response(int fd, int data, int response);

#ifdef __cplusplus
}
#endif

#endif

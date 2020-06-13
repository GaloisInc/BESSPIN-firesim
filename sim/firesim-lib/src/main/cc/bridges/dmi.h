#ifndef __DMI_H
#define __DMI_H

#include "serial.h"
#include <signal.h>

#ifdef DMIBRIDGEMODULE_struct_guard
class dmi_t: public bridge_driver_t
{
    public:
        dmi_t(simif_t* sim, DMIBRIDGEMODULE_struct * mmio_addrs);
        ~dmi_t();
        virtual void tick();
        virtual void init();
        virtual void finish();
        virtual bool terminate() { return false; }
        virtual int exit_code() { return 0; }

    private:
        DMIBRIDGEMODULE_struct * mmio_addrs;
        void send_req();
        void recv_resp();
	int sock;
	int fd;
};
#endif // DMIBRIDGEMODULE_struct_guard

#endif // __DMI_H

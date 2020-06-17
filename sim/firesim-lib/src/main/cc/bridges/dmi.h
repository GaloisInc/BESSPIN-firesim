#ifndef __DMI_H
#define __DMI_H

#include "bridges/bridge_driver.h"
#include "fesvr/firesim_fesvr.h"

#ifdef DMIBRIDGEMODULE_struct_guard
class dmi_t: public bridge_driver_t
{
    public:
        dmi_t(simif_t* sim, const std::vector<std::string>& args, uint32_t mmint_present, DMIBRIDGEMODULE_struct * mmio_addrs);
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
	bool mmint_present;
	bool busy;
	bool memloaded;
};
#endif // DMIBRIDGEMODULE_struct_guard

#endif // __DMI_H

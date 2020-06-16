#ifndef __RANDOM_H
#define __RANDOM_H

#include "bridges/bridge_driver.h"
#include "fesvr/firesim_fesvr.h"

#ifdef RANDOMBRIDGEMODULE_struct_guard
class random_t: public bridge_driver_t
{
    public:
        random_t(simif_t* sim, const std::vector<std::string>& args, RANDOMBRIDGEMODULE_struct * mmio_addrs);
        ~random_t();
        virtual void tick();
        virtual void init();
        virtual void finish();
        virtual bool terminate() { return false; }
        virtual int exit_code() { return 0; }

    private:
        RANDOMBRIDGEMODULE_struct * mmio_addrs;
        void fill();
	FILE* random_fd;
	uint32_t threshold;
	bool override_threshold;
};
#endif // RANDOMBRIDGEMODULE_struct_guard

#endif // __RANDOM_H

// Note: struct_guards just as in the headers
#ifdef RANDOMBRIDGEMODULE_struct_guard

#include "random.h"
#include <sys/stat.h>

#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <string>

random_t::random_t(simif_t* sim, const std::vector<std::string>& args,
             RANDOMBRIDGEMODULE_struct * mmio_addrs): bridge_driver_t(sim)
{
    this->mmio_addrs = mmio_addrs;
    this->random_fd = NULL;
    this->threshold = 0;
    this->count = 0;
    this->override_threshold = false;

    std::string threshold_arg = std::string("+random_threshold=");

    for (auto &arg: args) {
        if (arg.find(threshold_arg) == 0) {
            this->threshold = atoi(const_cast<char*>(arg.c_str()) + threshold_arg.length());
            this->override_threshold = true;
        }
    }

    printf("Random Bridge device present\n");
}

random_t::~random_t() {
    free(this->mmio_addrs);
}

void random_t::init() {
    if (this->override_threshold) {
        write(this->mmio_addrs->threshold_value, this->threshold);
        printf("[RAND] Setting threshold to user provided value = %d\n", this->threshold);
    } else {
        this->threshold = read(this->mmio_addrs->threshold_value);
        printf("[RAND] Read threshold value from hardware = %d\n", this->threshold);
    }
    this->random_fd = fopen("/dev/urandom", "r");
    if (this->random_fd == NULL) {
        printf("[RAND] Error opening /dev/urandom = %d\n", this->random_fd);
    }
}

void random_t::finish() {
    if (this->random_fd != NULL) {
        printf("[RAND] Closing random device. Sent %d bytes to target\n", this->count*4);
        fclose(random_fd);
    }
}

void random_t::fill() {
    uint32_t random_val;
    ssize_t result;
    while (read(this->mmio_addrs->in_ready)) {
       result = fread(&random_val, sizeof(random_val), 1, this->random_fd);
       if (result < 0) {
           printf("[RAND] error reading from /dev/urandom = %d\n", result);
       } else {
           // printf("[RAND] Writing to target: count = %03d | data = 0x%x\n", count, random_val);
           write(this->mmio_addrs->in_bits, random_val);
           write(this->mmio_addrs->in_valid, true);
           this->count++;
       }
    }
}

void random_t::tick() {
    if (this->random_fd != NULL) {
        if (read(this->mmio_addrs->threshold_reached)) { this->fill(); }
    }
}
#endif // RANDOMBRIDGEMODULE_struct_guard

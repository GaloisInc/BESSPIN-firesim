    #ifdef NUMCLIENTSCONFIG
    #define NUMPORTS 2
    #define NUMDOWNLINKS 2
    #define NUMUPLINKS 0
    #endif
    #ifdef PORTSETUPCONFIG
    ports[0] = new ShmemPort(0, "0000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000", false);
    ports[1] = new SSHPort(1);

    #endif
    
    #ifdef MACPORTSCONFIG
    uint16_t mac2port[3]  {1, 2, 0};
    #endif

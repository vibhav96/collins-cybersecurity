#include <sys/time.h>

int main(int argc, char **argv) {
	void *p;
	(void)argc; (void)argv;
	p=(void*)(gettimeofday);
	return 0;
}

#include <stdio.h>
#include <string.h>

// Buffer overflow
void getInput(char *input) {
    char buffer[10];
    strcpy(buffer, input);
}

// Magic numbers, bad naming
int chk(int x) {
    if (x > 17 && x < 65) return 1;
    return 0;
}

#include <stdio.h>

#include "common.h"
#include "compiler.h"
#include "scanner.h"


void compile(const char* source) {
  initScanner(source);
  int line = -1;
  for (;;) {
    Token token = scanToken();
    if (token.line != line) {
      printf("%4d ", token.line);
      line = token.line;
    } else {
      printf("   | ");
    }
    // `*s` allows us to pass in the precision (where to stop printing the string). We need this since
    // the original string doesn't have a terminator at the end.
    printf("%2d '%.*s'\n", token.type, token.length, token.start);

    if (token.type == TOKEN_EOF) break;
  }
}

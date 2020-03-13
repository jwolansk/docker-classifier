#!/bin/sh
find . -name '*.jpg' -execdir mogrify -resize 53x40! {} \;
find . -name '*.jpg' -execdir mogrify -crop 53x27+0+13 {} \;

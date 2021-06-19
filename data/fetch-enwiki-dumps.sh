#!/usr/bin/env bash

HOMEPAGE=http://www.mattmahoney.net/dc/text.html

echo "Fetch English Wikipedia dumps from Matt Mahoney site ($HOMEPAGE)"

wget -c -q --show-progress \
    http://www.mattmahoney.net/dc/enwik8.zip \
    http://www.mattmahoney.net/dc/enwik9.zip

unzip "enwiki[89].zip"

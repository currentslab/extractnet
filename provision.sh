#!/bin/bash

cython --cplus extractnet/*.pyx
cython --cplus extractnet/features/*.pyx
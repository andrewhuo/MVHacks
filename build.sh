#!/usr/bin/env bash

pygbag --build game/main.py

rm -rf frontend/build

mv game/build frontend/build
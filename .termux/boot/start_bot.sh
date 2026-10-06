#!/data/data/com.termux/files/usr/bin/bash
termux-wake-lock
cd ~/
nohup bash -c 'while true; do python main.py; sleep 5; done' > bot.log 2>&1 &
 

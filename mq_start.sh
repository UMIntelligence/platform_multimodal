#!/bin/bash
#docker exec {容器} tail -f nohup.out

nohup python manage.py sd_func_invoker &
nohup python manage.py sd_func_invoker_delay &

for i in {1..6}
do
   nohup python manage.py image_func_invoker &
   nohup python manage.py tts_func_invoker &
done

nohup python manage.py image_func_invoker_delay &
nohup python manage.py tts_func_invoker_delay &

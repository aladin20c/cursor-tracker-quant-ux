Find and kill the process using port 5000

In your terminal:
lsof -i :5001

You’ll see something like:
COMMAND   PID   USER   FD   TYPE ...
ControlCe 1234  ala    ...

Then kill it:
kill -9 1234


python3 ./backend/app.py
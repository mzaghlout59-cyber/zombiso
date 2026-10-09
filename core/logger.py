from datetime import datetime

def log(message):
    line = f'{datetime.now()} - {message}'
    with open('logs/city.log', 'a') as f:
        f.write(line + '\n')

#!/usr/bin/python3

import sys
import os
import sqlite3
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for
import rrdtool
import time
import random
import threading

from flask_debugtoolbar import DebugToolbarExtension

DB_FILE="/opt/TrafficControl/"

# Create a Thread Local Storage Object for Each Thread
local = threading.local()

def get_conn():
    """Return a thread-local SQLite connection."""
    # Checking if the current thread has a connection object
    if not hasattr(local, 'conn'):
        # If not, create a new connection object
        local.conn = sqlite3.connect(DB_FILE + 'traffic.db', check_same_thread=False)
    return local.conn


app = Flask(__name__)

app.config['SECRET_KEY'] = 'supersecretkey'
app.config['DEBUG_TB_ENABLED'] = True

app.jinja_env.globals.update(zip=zip)


# Connecting to a SQLite3 database
conn = sqlite3.connect(DB_FILE + 'traffic.db')
c = conn.cursor()



@app.route('/')
def index():
    # Connect to database and retrieve all IP addresses
    conn = sqlite3.connect(DB_FILE + 'traffic.db')
    c = conn.cursor()
    c.execute('SELECT ip_address FROM ip_addresses')
    ip_addresses = [row[0] for row in c.fetchall()]
    conn.close()

    # Choose a random IP address from the list
    ip_address = ip_addresses[0]

    # Render the HTML template and pass in the IP address variable
    return render_template('index.html', ip_address=ip_address)

# Function to get traffic data from the database
def get_traffic_data(ip_address, period):
    conn = sqlite3.connect(DB_FILE + 'traffic.db')
    cursor = conn.cursor()

    if period == 'hour':
        cursor.execute("SELECT timestamp, in_bytes, out_bytes FROM traffic WHERE ip_address = ? AND timestamp >= strftime('%s', 'now') - 3600 ORDER BY timestamp", (ip_address,))
    elif period == 'day':
        cursor.execute("SELECT timestamp, in_bytes, out_bytes FROM traffic WHERE ip_address = ? AND timestamp >= strftime('%s', 'now') - 86400 ORDER BY timestamp", (ip_address,))
    elif period == 'week':
        cursor.execute("SELECT timestamp, in_bytes, out_bytes FROM traffic WHERE ip_address = ? AND timestamp >= strftime('%s', 'now') - 604800 ORDER BY timestamp", (ip_address,))
    elif period == 'month':
        cursor.execute("SELECT timestamp, in_bytes, out_bytes FROM traffic WHERE ip_address = ? AND timestamp >= strftime('%s', 'now') - 2592000 ORDER BY timestamp", (ip_address,))
    elif period == 'year':
        cursor.execute("SELECT timestamp, in_bytes, out_bytes FROM traffic WHERE ip_address = ? AND timestamp >= strftime('%s', 'now') - 31536000 ORDER BY timestamp", (ip_address,))
    else:
        cursor.execute("SELECT timestamp, in_bytes, out_bytes FROM traffic WHERE ip_address = ? ORDER BY timestamp", (ip_address,))

    data = cursor.fetchall()
    conn.close()
    return data, [row[1] for row in data], [row[2] for row in data] #, [row[3] for row in data]


def get_connect():
    connect = sqlite3.connect(DB_FILE + 'traffic.db', check_same_thread=False)
    return connect

def traffic_get_total_data(ip_address):
    conn = get_connect()
    c = conn.cursor()

    periods = ['hour', 'day', 'week', 'month', 'year']
    totaltr = {}

    for period in periods:
        if period == 'hour':
            c.execute("SELECT SUM(total_in_pks), SUM(total_out_pks) FROM traffic WHERE ip_address=? AND timestamp>=datetime('now','-1 hour')", (ip_address,))
        elif period == 'day':
            c.execute("SELECT SUM(total_in_pks), SUM(total_out_pks) FROM traffic WHERE ip_address=? AND timestamp>=datetime('now','-24 hour')", (ip_address,))
        elif period == 'week':
            c.execute("SELECT SUM(total_in_pks), SUM(total_out_pks) FROM traffic WHERE ip_address=? AND timestamp>=datetime('now','-7 day')", (ip_address,))
        elif period == 'month':
            c.execute("SELECT SUM(total_in_pks), SUM(total_out_pks) FROM traffic WHERE ip_address=? AND timestamp>=datetime('now','-1 month')", (ip_address,))
        elif period == 'year':
            c.execute("SELECT SUM(total_in_pks), SUM(total_out_pks) FROM traffic WHERE ip_address=? AND timestamp>=datetime('now','-1 year')", (ip_address,))

        rows = c.fetchall()
        period_in_bytes = rows[0][0] if rows[0][0] is not None else 0
        period_out_bytes = rows[0][1] if rows[0][1] is not None else 0

        total_bytes = period_in_bytes + period_out_bytes
        # round(num, 2)
        totaltr[period] = {'total_in_bytes': round( period_in_bytes, 2) , 'total_out_bytes': round( period_out_bytes, 2 ), 'total_bytes': round( total_bytes, 2 ) }

    conn.close()
    return totaltr


def traffic_get_data(ip_address):
    conn = get_conn()
    c = conn.cursor()

    periods = ['hour', 'day', 'week', 'month', 'year']
    datatr = {}

    for period in periods:
        if period == 'hour':
            c.execute("SELECT SUM(in_pks), SUM(out_pks) FROM traffic WHERE ip_address=? AND timestamp>=datetime('now','-1 hour')", (ip_address,))
        elif period == 'day':
            c.execute("SELECT SUM(in_pks), SUM(out_pks) FROM traffic WHERE ip_address=? AND timestamp>=datetime('now','-24 hour')", (ip_address,))
        elif period == 'week':
            c.execute("SELECT SUM(in_pks), SUM(out_pks) FROM traffic WHERE ip_address=? AND timestamp>=datetime('now','-7 day')", (ip_address,))
        elif period == 'month':
            c.execute("SELECT SUM(in_pks), SUM(out_pks) FROM traffic WHERE ip_address=? AND timestamp>=datetime('now','-1 month')", (ip_address,))
        elif period == 'year':
            c.execute("SELECT SUM(in_pks), SUM(out_pks) FROM traffic WHERE ip_address=? AND timestamp>=datetime('now','-1 year')", (ip_address,))

        rows = c.fetchall()
        period_in_bytes = rows[0][0] if rows[0][0] is not None else 0
        period_out_bytes = rows[0][1] if rows[0][1] is not None else 0

        total_bytes = period_in_bytes + period_out_bytes
        # round(num, 2)
        datatr[period] = {'in_bytes': round( period_in_bytes, 2) , 'out_bytes': round( period_out_bytes, 2 ), 'total_bytes': round( total_bytes, 2 ) }

    conn.close()
    return datatr

# Function to update data in the database and create charts RRDtool
def update_traffic_data(ip_address, in_bytes, out_bytes ):

    conn = get_conn()
    c = conn.cursor()

    # Getting the current time
    now = int(datetime.now().strftime('%s'))

    # Checking if an IP address exists in the ip_addresses table
    c.execute("SELECT id FROM ip_addresses WHERE ip_address=?", (ip_address,))
    row = c.fetchone()
    if row is not None:
        ip_id = row[0]
    else:
        # If the IP address is not in the ip_addresses table, add it
        c.execute("INSERT INTO ip_addresses (ip_address) VALUES (?)", (ip_address,))
        ip_id = c.lastrowid

        return True

# Function to get a list of existing IP addresses from a database
def get_ip_addresses():
    conn = sqlite3.connect(DB_FILE + 'traffic.db')
    cursor = conn.cursor()
    cursor.execute("SELECT ip_address, comment FROM ip_addresses")
    data = cursor.fetchall()
    conn.close()
    return [(row[0], row[1]) for row in data]

# Traffic View Page
@app.route('/traffic_data')
def traffic_data():
    ip_address = request.args.get('ip_address')
    period = request.args.get('period')
    # Get traffic data
    data, in_bytes, out_bytes = get_traffic_data(ip_address, period)

    # Getting a comment by IP address
    conn = sqlite3.connect(DB_FILE + 'traffic.db')
    cursor = conn.cursor()
    cursor.execute("SELECT comment FROM ip_addresses WHERE ip_address = ?", (ip_address,))
    comment = cursor.fetchone()[0]
    conn.close()

    # Formation of a string for displaying IP and comment
    if comment:
        ip_string = f"{ip_address} - {comment}"
    else:
        ip_string = ip_address


    period_map = {
        'hour': ['end-1h', 'hour'],
        'day': ['end-24h', 'day'],
        'week': ['end-1w', 'week'],
        'month': ['end-1m', 'month'],
        'year': ['end-1y', 'year']
    }

    for period in ('hour', 'day', 'week', 'month', 'year'):
        rrd_file = DB_FILE + f'rrd/{ip_address}-{period}.rrd'
        img_file = DB_FILE + f'static/{ip_address}-{period}.png'
        start_time = period_map[period][0]
        step = period_map[period][1]

        rrdtool.graph(img_file,
            '--start', start_time,
            '--end', 'now',
            '--rigid',
            #"--color", "BACK#000000",
            "--color", "BACK#FFFFFF",
            #"--color", "CANVAS#000000",
            "--color", "CANVAS#FFFFFF",
            "--color", "FONT#000000",
            #"--color", "FONT#FFFFFF",
            "--color", "AXIS#FFFFFF",
            #"--color", "AXIS#000000",
            #"--color", "SHADEA#000000",
            #"--color", "SHADEB#000000",
            #"--color", "SHADEB#000000",
            "--color", "GRID#808080",
            "--color", "MGRID#808080",
            "--color", "FRAME#FFFFAA",
            #"--color", "FRAME#000000",
            "--color", "ARROW#FFFFFF",
            #"--color", "ARROW#000000",
            '-v', 'Mbps',
            '--width', '1280',
            '--height', '520',
            '--border', '2',
            '--slope-mode',
            '--no-gridfit',
            '--lower-limit', '0',
            '--font', 'DEFAULT:10',
            '--title', period_map[period][1].capitalize() + ' ' +     'Mbps',
            '--font', 'TITLE:14',
            f'DEF:input={rrd_file}:in_bytes:AVERAGE',
            f'DEF:output={rrd_file}:out_bytes:AVERAGE',
            'COMMENT: \\n',
            f'AREA:input#f5f5f5',
            f'LINE1:input#ff0000:In\t',
            f'GPRINT:input:LAST:Last\: %3.2lf Mbps\t',
            f'GPRINT:input:AVERAGE:Avg\: %3.2lf Mbps\t',
            f'GPRINT:input:MAX:Max\: %3.2lf Mbps\\n',
            f'LINE1:output#0000FF:Out\t',
            f'GPRINT:output:LAST:Last\: %3.2lf Mbps\t',
            f'GPRINT:output:AVERAGE:Avg\: %3.2lf Mbps\t',
            f'GPRINT:output:MAX:Max\: %3.2lf Mbps\\n',
            f'CDEF:in_byts=input,',
            f'CDEF:out_byts=output,')


    conn = sqlite3.connect(DB_FILE + 'traffic.db')
    cursor = conn.cursor()
    cursor.execute("SELECT ip_address, comment FROM ip_addresses")
    data = cursor.fetchall()
    conn.close()

    ip_addresses = [(row[0], row[1]) for row in data]

    _ip_addresses = [ row[0] for row in data  ]
    _comments = [ row[1] for row in data  ]

    datatr = traffic_get_data(ip_address)

    # Return HTML page with traffic data and graph links
    return render_template('traffic_data.html',
            comments=_comments,
            ip_address=ip_address,
            period=period,
            data=data,
            comment=comment,
            ip_addresses=_ip_addresses,
            datatr = traffic_get_data(ip_address),
            img_hour='static/{0}-hour.png'.format(ip_address),
            img_day='static/{0}-day.png'.format(ip_address),
            img_week='static/{0}-week.png'.format(ip_address),
            img_month='static/{0}-month.png'.format(ip_address),
            img_year='static/{0}-year.png'.format(ip_address))


@app.route('/ip_addresses')
def ip_addresses():
    conn = sqlite3.connect(DB_FILE + 'traffic.db')
    cursor = conn.cursor()
    cursor.execute("SELECT ip_address, comment FROM ip_addresses")
    data = cursor.fetchall()
    conn.close()

    ip_addresses = [(row[0], row[1]) for row in data]

    _ip_addresses = [ row[0] for row in data  ]
    _comments = [ row[1] for row in data  ]

    return render_template('ip_addresses.html', ip_addresses=_ip_addresses, comments=_comments )

from jinja2 import Environment, FileSystemLoader
from filters import formatBytes

app.jinja_env.filters['formatBytes'] = formatBytes

try:
 listen_ip=sys.argv[1]
 listen_port=sys.argv[2]
 device=sys.argv[3]
except IndexError:
 pass

@app.route('/channel', methods=['GET'])
def channel():
    channel = request.args.get('channel')

    period_map = {
        'hour': ['end-1h', 'hour'],
        'day': ['end-24h', 'day'],
        'week': ['end-1w', 'week'],
        'month': ['end-1m', 'month'],
        'year': ['end-1y', 'year']
    }

    for period in ('hour', 'day', 'week', 'month', 'year'):
        rrd_file = DB_FILE + f'rrd/{device}-{period}.rrd'
        img_file = DB_FILE + f'static/{device}-{period}.png'
        start_time = period_map[period][0]

        rrdtool.graph(img_file,
            '--start', start_time,
            '--end', 'now',
            '--rigid',
            #"--color", "BACK#000000",
            "--color", "BACK#FFFFFF",
            #"--color", "CANVAS#000000",
            "--color", "CANVAS#FFFFFF",
            "--color", "FONT#000000",
            #"--color", "FONT#FFFFFF",
            "--color", "AXIS#FFFFFF",
            #"--color", "AXIS#000000",
            #"--color", "SHADEA#FFFFFF",
            #"--color", "SHADEB#000000",
            #"--color", "SHADEA#FFFFFF",
            "--color", "GRID#808080",
            "--color", "MGRID#808080",
            "--color", "FRAME#FFFFAA",
            #"--color", "FRAME#000000",
            "--color", "ARROW#FFFFFF",
            #"--color", "ARROW#000000",
            '-v', 'Mbps',
            '--width', '1280',
            '--height', '520',
            '--border', '1',
            '--slope-mode',
            '--no-gridfit',
            '--lower-limit', '0',
            '--font', 'DEFAULT:10',
            '--title', period_map[period][1].capitalize() + ' ' +     'Mbps',
            '--font', 'TITLE:14',
            '--right-axis-label', '',
            f'DEF:input={rrd_file}:in_bytes:AVERAGE',
            f'DEF:output={rrd_file}:out_bytes:AVERAGE',
            'COMMENT: \\n',
            f'AREA:input#f5f5f5',
            f'LINE1:input#ff0000:In\t',
            f'GPRINT:input:LAST:Last\: %3.2lf Mbps\t',
            f'GPRINT:input:AVERAGE:Avg\: %3.2lf Mbps\t',
            f'GPRINT:input:MAX:Max\: %3.2lf Mbps\\n',
            f'LINE1:output#0000FF:Out\t',
            f'GPRINT:output:LAST:Last\: %3.2lf Mbps\t',
            f'GPRINT:output:AVERAGE:Avg\: %3.2lf Mbps\t',
            f'GPRINT:output:MAX:Max\: %3.2lf Mbps\\n',
            f'CDEF:in_byts=input,',
            f'CDEF:out_byts=output,')


    conn = sqlite3.connect(DB_FILE + 'traffic.db')
    cursor = conn.cursor()
    cursor.execute("SELECT ip_address, comment FROM ip_addresses")
    data = cursor.fetchall()
    conn.close()

    _ip_addresses = [ row[0] for row in data  ]
    _comments = [ row[1] for row in data  ]

    #return redirect(url_for('channel.html')) #, channel='wlan0'))
    return render_template('channel.html',
                            channel=device,
                            totaltr=traffic_get_total_data('127.0.0.1'),
                            ip_addresses=_ip_addresses,
                            comments=_comments)



@app.route('/add_ip_address', methods=['POST'])
def add_ip_address():
    ip_address = request.form['ip_address']
    comment = request.form['comment'] # get the comment from the form if it was entered
    conn = sqlite3.connect(DB_FILE + 'traffic.db')
    conn.execute("INSERT INTO ip_addresses (ip_address, comment) VALUES (?, ?)", (ip_address, comment))
    conn.commit()
    conn.close()

    # Creating an RRD file for a new IP address
    for period in ('hour', 'day', 'week', 'month', 'year'):
        rrd_file = DB_FILE + 'rrd/{0}-{1}.rrd'.format(ip_address, period)
        if not os.path.isfile(rrd_file):
           rrdtool.create(rrd_file,
            '--start', str(int(time.time()) - 360),
            '--step', '60',
            'DS:in_bytes:GAUGE:600:U:U',
            'DS:out_bytes:GAUGE:600:U:U',
            'RRA:AVERAGE:0.5:1:600',
            'RRA:AVERAGE:0.5:6:700',
            'RRA:AVERAGE:0.5:24:775',
            'RRA:AVERAGE:0.5:288:797',
            'RRA:MAX:0.5:1:600',
            'RRA:MAX:0.5:6:700',
            'RRA:MAX:0.5:24:775',
            'RRA:MAX:0.5:288:797')

    return redirect(url_for('traffic_data', ip_address=ip_address, period='hour'))


@app.route('/delete_ip_address', methods=['POST'])
def delete_ip_address():
    ip_address = request.form['ip_address']
    conn = sqlite3.connect(DB_FILE + 'traffic.db')
    conn.execute("DELETE FROM ip_addresses WHERE ip_address = ?", (ip_address,))
    conn.execute("DELETE FROM traffic WHERE ip_address = ?", (ip_address,))
    for period in ('hour', 'day', 'week', 'month', 'year'):
        rrd_file = DB_FILE + 'rrd/{0}-{1}.rrd'.format(ip_address, period)
        rrd_img = DB_FILE + 'static/{0}-{1}.png'.format(ip_address, period)
        if os.path.isfile(rrd_file):
           os.remove(rrd_file)
        if os.path.isfile(rrd_img):
           os.remove(rrd_img)
    conn.commit()
    conn.close()

    return redirect(url_for('channel'))


if __name__ == '__main__':
    try:
      app.run(host=listen_ip, port=listen_port, debug=True)
    except NameError:
        print( "Please run command: ./traffic_count.py IP PORT DEVICE" )

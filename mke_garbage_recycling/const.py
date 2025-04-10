DOMAIN = "mke_garbage_recycling"
PLATFORMS = ["sensor"]

# Configuration Keys
CONF_ADDRESS_NUMBER = "address_number"
CONF_STREET_DIRECTION = "street_direction"
CONF_STREET_NAME = "street_name"
CONF_STREET_SUFFIX = "street_suffix"

# API Details
BASE_URL = "https://itmdapps.milwaukee.gov/DpwServletsPublic/garbage_day"
REQUEST_PARAMS = {"embed": "y"}
REQUEST_HEADERS = {"Content-Type": "application/x-www-form-urlencoded"}

# Sensor Names
SENSOR_GARBAGE = "Garbage Pickup"
SENSOR_RECYCLING = "Recycling Pickup"

# Update Interval (optional, default is usually 60 seconds for sensors)
# from datetime import timedelta
# SCAN_INTERVAL = timedelta(hours=12)

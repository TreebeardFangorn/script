import streamlit as st
import requests
import datetime
from copy import deepcopy
from bs4 import BeautifulSoup
import pandas as pd
import sys

# Constants
DEFAULT_CHART_DATA = {'command': 'new', 'index': '0', 'lang': 'en'}
CHART_URL = 'https://astro.cafeastrology.com/natal.php'
RELATION_URL_TEMPLATE = 'https://astro.cafeastrology.com/synastry.php?index={}&index2={}'
LOCATION_OPTIONS = [
    'Dallas,48,1,32.78,-96.80',  # Central
    'Honolulu,15,1,21.30,-157.85',  # Hawaii
    'Sacramento,6,1,38.58,-121.48',  # West Coast
    'Seattle,53,1,47.60,-122.33',  # West Coast
    'Denver,8,1,39.73,-104.98',  # Mountain
    'Miami,12,1,25.77,-80.18',  # East Coast
    'Manhattan,36,1,40.79,-73.96',  # East Coast 2
    'Nashville,47380,1,36.17,-86.78',
    'Cincinnati,39038,1,39.15,-84.45',
    'Vancouver,2,2,49.27,-123.12',  # Canada
    'Calgary,1,2,51.02,-114.02',  # Canada
    'Mexico,252,52,19.42,-99.17',  # Mexico
    'Hyderabad,0,91,17.37,78.43',  # India
    'London,1,44,51.50,-0.17',  # England
    'Madrid,0,34,40.43,-3.70',  # Spain
    'Berlin,0,49,52.53,13.42',  # Germany
    'Istanbul,0,90,41.01,28.98',  # Turkey
    'Jerusalem,294,972,31.77,35.21',  # Israel
    'Cairo,0,20,30.03,31.35',  # Egypt
    'Paris,75,33,48.87,2.33',  # France
    'Tokyo,0,81,35.67,139.75',  # Japan
    'Beijing,0,86,39.92,116.42',  # China
    'Moscow,3,7,55.75,37.60',  # Moscow
    'Rome,0,39,41.75,12.25',  # Italy
    'Pretoria,0,27,-25.75,28.17',  # South Africa
    'Budapest,0,36,47.48,19.08',
    'Brisbane,6,61,-27.47,153.03',  # Australia
    'Reykjavik,0,354,64.17,-21.95',  # Iceland
    'Manila,0,63,14.58,120.98',
    'Melbourne,9,61,-37.82,144.97',  # Australia
    'Seoul,0,82,37.63,127.00',  # Korea
]
PREDEFINED_USERS = [
    ('Ar', 273725830),
    ('Da', 273732925),
    ('Am', 273000806),
]
CHART_COLUMNS = ['Sun_D', 'Moon_D', 'Mercury_D', 'Mars_D', 'Venus_D', 'Jupiter_D', 'Saturn_D', 'Uranus_D', 'Neptune_D', 'Pluto_D', 'N Node_D', 'Lilith_D']

# HTTP request headers
headers = {
    'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9',
    'cache-control': 'max-age=0',
    'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_12_2) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/103.0.0.0 Safari/537.36',
    'sec-ch-ua': '".Not/A)Brand";v="99", "Google Chrome";v="103", "Chromium";v="103"',
    'accept-language': 'en-US,en;q=0.9',
    'connection': 'keep-alive',
    'upgrade-insecure-requests': '1',
}

# Global variable
SKIP_HOUSES = True  # Default to skipping houses

# Helper functions
def get_planet_to_sign(all_tables):
    planet_to_sign = {}
    table_text = all_tables[2].get_text('|').lstrip('Zodiac : Tropical').strip().split('\n')
    for row in table_text:
        pln, position = row.split('|')[1], row.split('|')[2]
        planet_to_sign[pln] = position
    return planet_to_sign

def get_house_to_sign(all_tables):
    house_to_sign = {}
    table_text = all_tables[3].get_text('|').lstrip('Placidus').strip().split('\n')
    for row in table_text:
        house, sign = row.split('|')[1], row.split('|')[2]
        house_to_sign[house] = sign
    return house_to_sign

def get_planet_to_house(all_tables):
    planet_to_house = {}
    rows = all_tables[4].findChildren(['tr'])
    for row in rows:
        row_text = row.get_text()
        planet, house = row_text.split(' in ')
        planet_to_house[planet + '_H'] = house
    return planet_to_house

def get_planet_to_sign_decan(all_tables):
    planet_to_sign = {}
    table_text = all_tables[2].get_text('|').lstrip('Zodiac : Tropical').strip().split('\n')
    for row in table_text:
        pln, position = row.split('|')[1], row.split('|')[2]
        deg, minutes = row.split('|')[3].split("\u00b0")
        deg = float(deg)
        minutes = float(minutes[:-1])
        total_deg = deg + minutes / 60.0
        decan_id = int(total_deg // 10) + 1
        planet_to_sign[pln + '_D'] = position + '_{}'.format(decan_id)
    return planet_to_sign

def get_house_to_sign_decan(all_tables):
    house_to_sign = {}
    table_text = all_tables[3].get_text('|').lstrip('Placidus').strip().split('\n')
    for row in table_text:
        house, sign = row.split('|')[1], row.split('|')[2]
        deg, minutes = row.split('|')[3].split("\u00b0")
        deg = float(deg)
        minutes = float(minutes[:-1])
        total_deg = deg + minutes / 60.0
        decan_id = int(total_deg // 10) + 1
        house_to_sign[house + '_D'] = sign + '_{}'.format(decan_id)
    return house_to_sign

def get_chart_from_html(html_text):
    chart = {}
    soup = BeautifulSoup(html_text, 'html.parser')
    all_tables = soup.find_all('table')
    chart.update(get_planet_to_sign(all_tables))
    if not SKIP_HOUSES:
        chart.update(get_house_to_sign(all_tables))
        chart.update(get_planet_to_house(all_tables))
    chart['html'] = html_text
    return chart

def get_user_id_and_chart_from_data(data):
    r = requests.post(CHART_URL, data=data, headers=headers)
    assert r.status_code == 200, 'Error when pulling data: {}, {}'.format(r.reason, r.text)
    user_id = r.text.split('/synastry.php?&index=')[-1].split('&')[0]
    chart = get_chart_from_html(r.text)
    return user_id, chart

def get_scores_from_user_ids(user_id_1, user_id_2):
    url = RELATION_URL_TEMPLATE.format(user_id_1, user_id_2)
    r = requests.get(url, headers=headers)
    assert r.status_code == 200, 'Error when pulling relation data: {}'.format(r.reason)
    soup = BeautifulSoup(r.text, 'html.parser')
    scores = soup.find_all('table')[0].get_text().split()[-3:]
    return [int(elem) for elem in scores], url

def get_name_from_datetime(datetime_obj):
    return str(hash(datetime_obj) + sys.maxsize + 1)

def get_new_user_data(curr_datetime, location, sex):
    data = deepcopy(DEFAULT_CHART_DATA)
    data['d1year'] = str(curr_datetime.year)
    data['d1month'] = str(curr_datetime.month)  # Corrected from '-Wesley'
    data['d1day'] = str(curr_datetime.day)
    data['d1hour'] = str(curr_datetime.hour)
    data['d1min'] = str(curr_datetime.minute)
    data['name'] = get_name_from_datetime(curr_datetime)
    data['sex'] = str(sex)
    data['citylist'] = location
    data['shareable'] = "true"
    if SKIP_HOUSES:
        data['nohouses'] = 'true'
    return data

def add_decans(chart):
    html_text = chart['html']
    soup = BeautifulSoup(html_text, 'html.parser')
    all_tables = soup.find_all('table')
    chart.update(get_planet_to_sign_decan(all_tables))
    if not SKIP_HOUSES:
        chart.update(get_house_to_sign_decan(all_tables))
    return chart

def get_chart_info(datetime_obj, location, sex):
    curr_data = get_new_user_data(datetime_obj, location, sex)
    curr_user_id, curr_chart = get_user_id_and_chart_from_data(curr_data)
    curr_chart = add_decans(curr_chart)
    return curr_user_id, curr_chart

# Main Streamlit app
def main():
    st.title("Astrology Chart Calculator")
    st.write("Enter your birth details to see your astrology chart and compatibility scores.")

    # User inputs
    year = st.number_input("Year", min_value=1900, max_value=2100, value=2000)
    month = st.number_input("Month", min_value=1, max_value=12, value=1)
    day = st.number_input("Day", min_value=1, max_value=31, value=1)
    include_time = st.checkbox("Include time (optional)")
    global SKIP_HOUSES  # Declare that we are modifying the global variable
    if include_time:
        hour = st.number_input("Hour", min_value=0, max_value=23, value=12)
        minute = st.number_input("Minute", min_value=0, max_value=59, value=0)
        SKIP_HOUSES = False
    else:
        hour = 12
        minute = 0
        SKIP_HOUSES = True

    location_options = [loc.split(',')[0] for loc in LOCATION_OPTIONS]
    location_index = st.selectbox("Location", options=range(len(location_options)), format_func=lambda x: location_options[x])
    location = LOCATION_OPTIONS[location_index]

    sex_options = ["Female", "Male"]
    sex = st.radio("Gender", options=sex_options)
    sex = 0 if sex == "Female" else 1

    # Calculate button
    if st.button("Calculate"):
        try:
            # Create datetime object
            curr_datetime = datetime.datetime(year=year, month=month, day=day, hour=hour, minute=minute)
            
            # Get chart info
            user_id, chart = get_chart_info(curr_datetime, location, sex)
            
            # Display birth chart
            chart_df = pd.DataFrame([chart])[CHART_COLUMNS]
            st.subheader("Your Birth Chart")
            st.dataframe(chart_df)
            chart_url = f"https://astro.cafeastrology.com/natal.php?index={user_id}"
            st.markdown(f"[View Full Chart]({chart_url})")

            # Display compatibility scores
            for compare_name, compare_user_id in PREDEFINED_USERS:
                scores, url = get_scores_from_user_ids(user_id, compare_user_id)
                pos, neg, total = scores
                result = {'Positive': pos, 'Negative': neg, 'Total': total}
                compat_df = pd.DataFrame([result])
                st.subheader(f"Compatibility with {compare_name}")
                st.dataframe(compat_df)
                st.markdown(f"[View Compatibility Report]({url})")

        except Exception as e:
            st.error(f"Oops! Something went wrong: {e}. Try again or check your inputs.")

if __name__ == '__main__':
    main()

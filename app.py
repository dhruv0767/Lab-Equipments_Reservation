import streamlit as st
import streamlit_authenticator as stauth
import pandas as pd
import yaml
from yaml.loader import SafeLoader
import datetime
import plotly.express as px
import json
from io import StringIO

st.set_page_config(layout="wide")

def load_json(file_path):
    with open(file_path, 'r') as file:
        return json.load(file)

equipment_details = load_json('equipment_details.json')

with open('config.yaml') as file:
    config = yaml.load(file, Loader=SafeLoader)

def save_equipment_details(details, json_file_path='equipment_details.json'):
    with open(json_file_path, 'w') as file:
        json.dump(details, file, indent=4)

authenticator = stauth.Authenticate(
    config['credentials'],
    config['cookie']['name'],
    config['cookie']['key'],
    config['cookie']['expiry_days'],
    config['pre-authorized']
)

authenticator.login()

# Filter equipment details to only include PCR-capable equipment
pcr_equipment_details = {room: equip for room, equip in equipment_details.items() if 'PCR' in equip}

def load_or_initialize_pcr_df():
    if 'pcr_reservations_df' not in st.session_state:
        st.session_state['pcr_reservations_df'] = pd.DataFrame(columns=['Username', 'Room', 'Equipment', 'Start_Time', 'End_Time'])
    return st.session_state['pcr_reservations_df']

pcr_reservations_df = load_or_initialize_pcr_df()

def convert_df_to_csv(df):
    output = StringIO()
    df.to_csv(output, index=False)
    return output.getvalue()

def generate_time_slots():
    return [{"label": f"Slot {i + 1}: {datetime.time(hour=h).strftime('%H:%M')}-{datetime.time(hour=h+3).strftime('%H:%M')}",
             "start": datetime.time(hour=h), "end": datetime.time(hour=h+3)}
            for i, h in enumerate(range(8, 20, 3))]

slots = generate_time_slots()

def check_and_submit_reservation(room, equipment, start, end):
    df = pcr_reservations_df
    overlapping = df[(df['Room'] == room) & (df['Equipment'] == equipment) &
                     (df['Start_Time'] < end) & (df['End_Time'] > start)]
    if not overlapping.empty:
        st.error("This slot is already booked. Please choose another slot.")
        return

    # Add new reservation
    new_reservation = {'Username': st.session_state['name'], 'Room': room, 'Equipment': equipment, 'Start_Time': start, 'End_Time': end}
    st.session_state['pcr_reservations_df'] = st.session_state['pcr_reservations_df'].append(new_reservation, ignore_index=True)
    st.success(f"Reservation successful from {start.strftime('%Y-%m-%d %H:%M')} to {end.strftime('%Y-%m-%d %H:%M')}")

if st.session_state["authentication_status"]:
    room = st.selectbox("Select a PCR-capable Room", list(pcr_equipment_details.keys()))
    equipment = st.selectbox("Select PCR Equipment", list(pcr_equipment_details[room].keys()))

    today = datetime.date.today()
    reservation_date = st.date_input("Reservation Date", min_value=today, max_value=today + datetime.timedelta(days=1))
    selected_slot_label = st.selectbox("Select a Time Slot", [slot['label'] for slot in slots])
    selected_slot = next(slot for slot in slots if slot['label'] == selected_slot_label)

    start_datetime = datetime.datetime.combine(reservation_date, selected_slot['start'])
    end_datetime = datetime.datetime.combine(reservation_date, selected_slot['end'])

    if st.button('Submit PCR Reservation'):
        check_and_submit_reservation(room, equipment, start_datetime, end_datetime)

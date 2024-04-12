import streamlit as st
import streamlit_authenticator as stauth
import pandas as pd
import yaml
from yaml.loader import SafeLoader
import datetime
import plotly.express as px
import json
from io import StringIO
import pytz

# Set your desired timezone
user_timezone = pytz.timezone('Asia/Bangkok')

def localize_datetime(dt):
    return dt.replace(tzinfo=pytz.utc).astimezone(user_timezone)

st.set_page_config(layout="wide")

with open('config.yaml') as file:
    config = yaml.load(file, Loader=SafeLoader)

@st.cache_data(show_spinner=False)
def load_or_initialize_df(key, columns):
    if key not in st.session_state:
        st.session_state[key] = pd.DataFrame(columns=columns)
    return st.session_state[key]

reservations_df = load_or_initialize_df('reservations_df', ['Username', 'Room', 'Equipment', 'Start_Time', 'End_Time'])
pcr_reservations_df = load_or_initialize_df('pcr_reservations_df', ['Username', 'Room', 'Equipment', 'Start_Time', 'End_Time'])

authenticator = stauth.Authenticate(
    config['credentials'],
    config['cookie']['name'],
    config['cookie']['key'],
    config['cookie']['expiry_days'],
    config['pre-authorized']
)

authenticator.login()

try:

    # Function to load equipment details from the JSON file
    @st.cache_data(show_spinner=False)
    def load_json(file_path):
        with open(file_path, 'r') as file:
            return json.load(file)
    
    equipment_details = load_json('equipment_details.json')
    
    # Function to save equipment details back to the JSON file
    def save_equipment_details(details, json_file_path='equipment_details.json'):
        with open(json_file_path, 'w') as file:
            json.dump(details, file, indent=4)
    
    @st.cache_data(show_spinner=False)
    def image_exists(image_path):
        import os
        return os.path.exists(image_path)
    
    def safe_display_image(image_path, width=100, offset=0):
        if image_exists(image_path):
            # Create columns where the first column acts as a left margin
            cols = st.columns([offset, 1])  # Adjust the ratio as needed
            with cols[1]:  # Place the image in the second column
                st.image(image_path, width=width)
        else:
            st.error("Image not available.")
    
    # Load equipment details from JSON instead of hardcoding
    room_equipment_details = equipment_details
    
    # Simulated admin usernames list - ensure this matches with your authenticator setup
    admin_usernames = ['GeneticsKU@Admins', 'Admins']
    
    # Custom CSS to increase tab size
    css = '''
    <style>
        .stTabs [data-baseweb="tab-list"] button [data-testid="stMarkdownContainer"] p {
        font-size:2rem; 
        margin-right: 25px;
        }
        /* Targeting based on data-testid attribute */
        [data-testid="stMarkdownContainer"] {
            font-size: 25px; /* Increase font size */
            color: White; /* Change text color */
            margin-left: 0px; /* Increase left margin */
        }
    </style>
    '''
    st.markdown(css, unsafe_allow_html=True)
    # Function to convert DataFrame to CSV
    def convert_df_to_csv(df):
        output = StringIO()
        df.to_csv(output, index=False)  # Optionally, set index=False to exclude DataFrame index
        return output.getvalue()
    
    
    @st.cache_data
    def generate_time_slots():
        slots = [{"label": f"Slot {i + 1}: {datetime.time(hour=h).strftime('%H:%M')}-{datetime.time(hour=h+3).strftime('%H:%M')}",
                  "start": datetime.time(hour=h), "end": datetime.time(hour=h+3)}
                 for i, h in enumerate(range(8, 20, 3))]
        return slots
    
    slots = generate_time_slots()
    
    
    def check_and_submit_reservation(selected_room, selected_equipment, start_datetime, end_datetime):
        # Ensure time columns are in datetime format
        st.session_state.pcr_reservations_df['Start_Time'] = pd.to_datetime(st.session_state.pcr_reservations_df['Start_Time'])
        st.session_state.pcr_reservations_df['End_Time'] = pd.to_datetime(st.session_state.pcr_reservations_df['End_Time'])
    
        # Convert to local time zone before processing
        start_datetime = localize_datetime(start_datetime)
        end_datetime = localize_datetime(end_datetime)
    
        # Check for continuous and overlapping bookings
        user_reservations = st.session_state.pcr_reservations_df[
            (st.session_state.pcr_reservations_df['Username'] == st.session_state["name"]) &
            (st.session_state.pcr_reservations_df['Room'] == selected_room) &
            (st.session_state.pcr_reservations_df['Equipment'] == selected_equipment) &
            (st.session_state.pcr_reservations_df['Start_Time'].dt.date == reservation_date)
            ]
    
        continuous_slot_booked = False
        for _, res in user_reservations.iterrows():
            if res['End_Time'] == start_datetime or res['Start_Time'] == end_datetime:
                continuous_slot_booked = True
                break
    
        overlapping_reservations = st.session_state.pcr_reservations_df[
            (st.session_state.pcr_reservations_df['Room'] == selected_room) &
            (st.session_state.pcr_reservations_df['Equipment'] == selected_equipment) &
            ((st.session_state.pcr_reservations_df['Start_Time'] < end_datetime) &
             (st.session_state.pcr_reservations_df['End_Time'] > start_datetime))
            ]
    
        if not overlapping_reservations.empty:
            st.error("This slot is already booked. Please choose another slot.")
        elif continuous_slot_booked:
            st.error("Cannot book continuous slots. Please select a non-continuous slot.")
        else:
            # Create and add new reservation
            new_reservation = {
                'Username': st.session_state["name"],
                'Room': selected_room,
                'Equipment': selected_equipment,
                'Start_Time': start_datetime,
                'End_Time': end_datetime
            }
            new_reservation_df = pd.DataFrame([new_reservation])
            st.session_state.pcr_reservations_df = pd.concat(
                [st.session_state.pcr_reservations_df, new_reservation_df], ignore_index=True)
            st.success(
                f"Reservation successful for {selected_equipment} from {start_datetime.strftime('%Y-%m-%d %H:%M')} to {end_datetime.strftime('%Y-%m-%d %H:%M')}")
    
    # Function to clear reservation data
    def clear_reservation_data():
        st.session_state.reservations_df = pd.DataFrame(columns=['Username', 'Room', 'Equipment', 'Start_Time', 'End_Time'])
        st.session_state.pcr_reservations_df = pd.DataFrame(columns=['Username', 'Room', 'Equipment', 'Start_Time', 'End_Time'])
        st.sidebar.success("All reservation data has been cleared.")
    
    # Admin Interface for enabling/disabling equipment
    if st.session_state.get("name") in admin_usernames:
        st.write(st.session_state.reservations_df)
        st.write(st.session_state.pcr_reservations_df)
        st.sidebar.write("Admin Interface")
        selected_room_admin = st.sidebar.selectbox("Select a room to manage equipment:",
                                                   list(room_equipment_details.keys()))
        equipment_list = list(room_equipment_details[selected_room_admin].keys())
        selected_equipment_admin = st.sidebar.selectbox("Select equipment to toggle availability:", equipment_list)
    
        if st.sidebar.button("Toggle Availability"):
            # Retrieve the current status of the selected equipment
            current_status = room_equipment_details[selected_room_admin][selected_equipment_admin]['enabled']
            # Toggle the 'enabled' status
            room_equipment_details[selected_room_admin][selected_equipment_admin]['enabled'] = not current_status
            # Show a success message on the sidebar
            st.sidebar.success(f"{'Disabled' if current_status else 'Enabled'} {selected_equipment_admin}")
    
            # Save the updated equipment details back to the JSON file
            save_equipment_details(room_equipment_details)
    
    # Button to clear all reservation data
        if st.sidebar.button("Clear All Reservations"):
            clear_reservation_data()
    
    # Check authentication status
    if st.session_state["authentication_status"]:
        # Successful login
        authenticator.logout(location='sidebar')
        # Use HTML to style the username with a specific color
        # Using more styles
        message = f"## Welcome <span style='color: White; font-size: 40px; font-family: Arial;'>{st.session_state['name']}</span>"
        st.markdown(message, unsafe_allow_html=True)
        tab1, tab2, tab3, tab4 = st.tabs(["Reservation Tables", "Reservation Forms", "Reservation Cancellation", "Contact Us"])
    
    
        def convert_df_to_csv(df):
            """Converts a DataFrame to a CSV string."""
            output = StringIO()
            df.to_csv(output, index=False)
            return output.getvalue().encode('utf-8')
    
    
        # Adding download buttons in the sidebar for each DataFrame
        st.sidebar.download_button(
            label="Download General Reservations as CSV",
            data=convert_df_to_csv(st.session_state.reservations_df),
            file_name='general_reservations.csv',
            mime='text/csv'
        )
    
        st.sidebar.download_button(
            label="Download PCR Reservations as CSV",
            data=convert_df_to_csv(st.session_state.pcr_reservations_df),
            file_name='pcr_reservations.csv',
            mime='text/csv'
        )
    
        with tab1:
            # st.subheader("Reservation Tables")
            room_selection = st.selectbox("### Select a Room", list(room_equipment_details.keys()),key='tab1 select room')
    
            # Allow users to select between today and tomorrow
            view_date = st.radio("### View reservations for", ("## Today", "## Tomorrow"))
            selected_date = datetime.date.today() if view_date == "## Today" else datetime.date.today() + datetime.timedelta(
                days=1)
    
            # Start by defining the full day and PCR operational hours for the selected date
            full_day_start = datetime.datetime.combine(selected_date, datetime.time(0, 0))
            full_day_end = datetime.datetime.combine(selected_date, datetime.time(23, 59))
            pcr_start = datetime.datetime.combine(selected_date, datetime.time(8, 0))
            pcr_end = datetime.datetime.combine(selected_date, datetime.time(20, 0))
    
            # Separate Gantt chart data for PCR and non-PCR equipment
            gantt_df_list_pcr = []
            gantt_df_list_non_pcr = []
    
            for equipment, details in room_equipment_details[room_selection].items():
                if details['enabled']:
                    is_pcr_equipment = "PCR" in equipment
                    reservations_df = st.session_state.pcr_reservations_df if is_pcr_equipment else st.session_state.reservations_df
                    reservations_df['Start_Time'] = pd.to_datetime(reservations_df['Start_Time'])
    
                    equipment_reservations = reservations_df[
                        (reservations_df['Room'] == room_selection) &
                        (reservations_df['Equipment'] == equipment) &
                        (reservations_df['Start_Time'].dt.date == selected_date)
                        ]
                    # Convert to local time zone before processing
                    start_datetime = localize_datetime(start_datetime)
                    end_datetime = localize_datetime(end_datetime)
    
                    target_list = gantt_df_list_pcr if is_pcr_equipment else gantt_df_list_non_pcr
                    operational_start = pcr_start if is_pcr_equipment else full_day_start
                    operational_end = pcr_end if is_pcr_equipment else full_day_end
    
                    if equipment_reservations.empty:
                        target_list.append({
                            'Task': equipment,
                            'Start': operational_end,
                            'Finish': operational_end,
                            'User': 'Available'
                        })
                    else:
                        for _, reservation in equipment_reservations.iterrows():
                            start = max(reservation['Start_Time'], operational_start) if is_pcr_equipment else reservation[
                                'Start_Time']
                            end = min(reservation['End_Time'], operational_end) if is_pcr_equipment else reservation[
                                'End_Time']
                            target_list.append({
                                'Task': equipment,
                                'Start': start,
                                'Finish': end,
                                'User': reservation['Username']
                            })
    
            # Generate and display the Gantt chart for PCR equipment
            if gantt_df_list_pcr:
                gantt_df_pcr = pd.DataFrame(gantt_df_list_pcr)
                fig_pcr = px.timeline(gantt_df_pcr, x_start="Start", x_end="Finish", y="Task", color="User",
                                      title=f"PCR Equipment Reservations for {room_selection}")
                fig_pcr.update_xaxes(range=[pcr_start, pcr_end], tickformat="%H:%M\n%Y-%m-%d", showgrid=True,
                                     gridcolor='LightGrey')
                fig_pcr.update_yaxes(showgrid=True, gridcolor='LightGrey')
                fig_pcr.update_layout(
                    title=dict(
                        text=f"Equipment Reservations for {room_selection}",
                        # Also corrected here if updating layout separately
                        font=dict(size=26),
                        x=0,
                        y=0.95,
                    ),
                    xaxis=dict(
                        title="Time",
                        title_font=dict(size=20),
                        tickfont=dict(size=18),
                        showgrid=True,
                        gridcolor="LightGrey",
                        side="top",
                        dtick=7200000,  # 2 hour in milliseconds
                        tickformat="%H:%M\n%Y-%m-%d"  # Adjust if needed to match your desired format
                    ),
                    yaxis=dict(
                        title="Equipment",
                        title_font=dict(size=20),
                        tickfont=dict(size=18),
                        showgrid=True,
                        gridcolor="LightGrey"
                    ),
                    margin=dict(t=200),  # Adjust if needed
                    height=600,
                    width=1000
                )
                for trace in fig_pcr.data:
                    if trace.name == "Available":
                        trace.showlegend = False
                st.plotly_chart(fig_pcr)
    
            # Generate and display the Gantt chart for non-PCR equipment
            if gantt_df_list_non_pcr:
                gantt_df_non_pcr = pd.DataFrame(gantt_df_list_non_pcr)
                fig_non_pcr = px.timeline(gantt_df_non_pcr, x_start="Start", x_end="Finish", y="Task", color="User",
                                          title=f"Non-PCR Equipment Reservations for {room_selection}")
                fig_non_pcr.update_xaxes(range=[full_day_start, full_day_end], tickformat="%H:%M\n%Y-%m-%d", showgrid=True,
                                         gridcolor='LightGrey')
                fig_non_pcr.update_yaxes(showgrid=True, gridcolor='LightGrey')
                fig_non_pcr.update_layout(
                    title=dict(
                        text=f"Equipment Reservations for {room_selection}",
                        # Also corrected here if updating layout separately
                        font=dict(size=26),
                        x=0,
                        y=0.95,
                    ),
                    xaxis=dict(
                        title="Time",
                        title_font=dict(size=20),
                        tickfont=dict(size=18),
                        showgrid=True,
                        gridcolor="LightGrey",
                        side="top",
                        dtick=7200000,  # 2 hour in milliseconds
                        tickformat="%H:%M\n%Y-%m-%d"  # Adjust if needed to match your desired format
                    ),
                    yaxis=dict(
                        title="Equipment",
                        title_font=dict(size=20),
                        tickfont=dict(size=18),
                        showgrid=True,
                        gridcolor="LightGrey"
                    ),
                    margin=dict(t=200),  # Adjust if needed
                    height=600,
                    width=1000
                )
                for trace in fig_non_pcr.data:
                    if trace.name == "Available":
                        trace.showlegend = False
    
                st.plotly_chart(fig_non_pcr)
    
        with tab2:
            # st.subheader("Reservation Form")
    
            # Room selection
            selected_room = st.selectbox("### Select a Room", list(room_equipment_details.keys()))
    
            # Equipment selection based on the selected room
            selected_equipment = st.selectbox("### Select Equipment", list(room_equipment_details[selected_room].keys()))
    
            # Fetch equipment information
            equipment_info = room_equipment_details[selected_room][selected_equipment]
    
            # Display selected equipment details and image
            safe_display_image(equipment_info['image'], width=450,offset= 0.5)  # Adjust width as necessary
            st.write(f"#### Details : {equipment_info['details']}")
    
            # Check if equipment is enabled before allowing reservation
            if equipment_info.get('enabled', True):  # Proceed if equipment is enabled
                if "PCR" in selected_equipment:
                    st.subheader("Book Your PCR Slot")
    
                    # Date and slot selection within the form to prevent re-run on change
                    today = datetime.date.today()
                    tomorrow = today + datetime.timedelta(days=1)
                    reservation_date = st.date_input("## Reservation Date", min_value=today, max_value=tomorrow)
    
                    current_datetime = datetime.datetime.now()
                    slots = generate_time_slots()  # Function to generate time slots
                    if reservation_date == today:
                        slots = [slot for slot in slots if
                                 datetime.datetime.combine(today, slot['end']) > current_datetime]
    
                    if slots:
                        available_slots = [slot['label'] for slot in slots]
                        selected_slot_label = st.selectbox("## Select a Time Slot", available_slots)
                        selected_slot = next((slot for slot in slots if slot['label'] == selected_slot_label), None)
                    else:
                        st.error("No available slots for the selected day.")
    
    
                    if st.button('### Submit PCR Reservation'):
                        start_datetime = datetime.datetime.combine(reservation_date, selected_slot['start'])
                        end_datetime = datetime.datetime.combine(reservation_date, selected_slot['end'])
                        # Convert to local time zone before processing
                        start_datetime = localize_datetime(start_datetime)
                        end_datetime = localize_datetime(end_datetime)
    
                        # Call function to check availability and submit reservation
                        check_and_submit_reservation(selected_room, selected_equipment, start_datetime, end_datetime)
    
    
                else:
                    # General reservation logic for non-PCR equipment
                    if "PCR" not in selected_equipment:
                        with st.form(key='NonPCR_Reservation_Form'):
                            st.subheader(f"Reserve {selected_equipment}")
    
                            tomorrow = datetime.date.today() + datetime.timedelta(days=1)
                            start_date = st.date_input("## Start Date", min_value=datetime.date.today(), max_value=tomorrow)
                            start_time = st.time_input("## Start Time", value=datetime.datetime.now().replace(second=0,
                                                                                                           microsecond=0).time())
                            end_time = st.time_input("## End Time",
                                                     value=(datetime.datetime.now() + datetime.timedelta(hours=1)).replace(
                                                         second=0, microsecond=0).time())
    
                            start_datetime = datetime.datetime.combine(start_date, start_time)
                            end_datetime = datetime.datetime.combine(start_date, end_time)
                            # Convert to local time zone before processing
                            start_datetime = localize_datetime(start_datetime)
                            end_datetime = localize_datetime(end_datetime)
    
                            submit_button = st.form_submit_button("### Submit Reservation")
    
                        if submit_button:
                            if start_datetime >= end_datetime:
                                st.error("The start time must be before the end time. Please adjust your selection.")
                            else:
                                # Check for overlapping reservations
                                overlapping_reservations = st.session_state.reservations_df[
                                    (st.session_state.reservations_df['Room'] == selected_room) &
                                    (st.session_state.reservations_df['Equipment'] == selected_equipment) &
                                    (st.session_state.reservations_df['Start_Time'] < end_datetime) &
                                    (st.session_state.reservations_df['End_Time'] > start_datetime)
                                    ]
    
                                if not overlapping_reservations.empty:
                                    st.error("This time slot is already reserved. Please choose another time.")
                                else:
                                    new_reservation = {
                                        'Username': st.session_state["name"],
                                        'Room': selected_room,
                                        'Equipment': selected_equipment,
                                        'Start_Time': start_datetime,
                                        'End_Time': end_datetime
                                    }
                                    new_reservation_df = pd.DataFrame([new_reservation])
                                    st.session_state.reservations_df = pd.concat(
                                        [st.session_state.reservations_df, new_reservation_df], ignore_index=True)
    
                                    st.success(
                                        f"Reservation successful for {selected_equipment} in {selected_room} from {start_datetime} to {end_datetime}")
            else:
                st.error("This equipment is currently not available for reservation.")
    
        with tab3:
            # st.subheader("Reservation Cancellation")
    
            # Assuming 'Username' in the reservations DataFrame is the authenticated user's identifier
            user_reservations = st.session_state.reservations_df[
                st.session_state.reservations_df['Username'] == st.session_state["name"]]
    
            if not user_reservations.empty:
                # Display the reservations in a selectbox and get the selected index
                selected_reservation_index = st.selectbox("## Your Reservations:",
                                                          options=range(len(user_reservations)),
                                                          format_func=lambda
                                                              x: f"{user_reservations.iloc[x]['Equipment']} on {user_reservations.iloc[x]['Start_Time'].strftime('%Y-%m-%d %H:%M')}")
    
                # Provide an option to cancel the selected reservation
                if st.button("### Cancel Reservation"):
                    # Remove the selected reservation from the DataFrame
                    reservation_to_cancel = user_reservations.iloc[selected_reservation_index]
                    st.session_state.reservations_df = st.session_state.reservations_df.drop(reservation_to_cancel.name)
                    st.success("Reservation canceled successfully.")
    
            else:
                st.write("You have no reservations.")
    
        with tab4:
            st.subheader("Error reports or Inconvenient issues")
    
            contact_form = """
            <form action="https://formsubmit.co/geneticsku.services@gmail.com" method="POST">
                 <input type="hidden" name="_captcha" value="false">
                 <input type="text" name="name" placeholder="Your name" required>
                 <input type="email" name="email" placeholder="Your email" required>
                 <textarea name="message" placeholder="Your message here"></textarea>
                 <button type="submit">Send</button>
            </form>
            """
    
            st.markdown(contact_form, unsafe_allow_html=True)
    
    
            # Use Local CSS File
            def local_css(file_name):
                with open(file_name) as f:
                    st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
    
    
            local_css("style/style.css")
    
    
    elif st.session_state["authentication_status"] is False:
        st.error('Username/password is incorrect')
    elif st.session_state["authentication_status"] is None:
        st.warning('Please enter your username and password')
    
except AttributeError:
    pass

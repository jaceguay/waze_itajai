# %%
import geopandas as gpd
import pandas as pd
from datetime import datetime, timedelta
import time
import paramiko
import io

# %%
# time.sleep(3 * 60)

# %%
# Definir username e password
username = "nome_usuario"
password = "senha_usuario"

# %%
def get_data(base_day, savepath):
    def read_file_over_ssh(filename, hostname, port, username, password):
        # Connect to the server
        client = paramiko.SSHClient()
        # Automatically add the server's host key
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(hostname, port, username, password)

        # Read the file
        sftp = client.open_sftp()
        with sftp.file(filename, "r") as file:
            data = file.read()

        # Close the connection
        client.close()

        return data

    def read_last_30_days(start_date):
        date = datetime.strptime(start_date, '%Y-%m-%d')
        frames = []
        for i in range(30):
            date_to_read = date - timedelta(days=i)
            file_path = f'/home/AD/03440857913/waze_feed/resultados/{date_to_read.year}/jams/{date_to_read.strftime("%Y-%m-%d")}_jams.json'
            print(file_path)

            file_content = read_file_over_ssh(
                filename=file_path,
                hostname="gdsegur.itajai.local",
                port=22,  # Use the correct port number if it's not the default SSH port
                username=username,
                password=password
            )

            gdf = gpd.read_file(io.BytesIO(file_content))
            frames.append(gdf)

        return gpd.GeoDataFrame(pd.concat(frames, ignore_index=True))

    # Read the data
    final_geo_data = read_last_30_days(base_day)

    # Extracting the day and hour portion from the timestamp
    final_geo_data['day'] = pd.to_datetime(
        final_geo_data['timestamp'], format='ISO8601').dt.date
    final_geo_data['hour'] = pd.to_datetime(
        final_geo_data['timestamp'], format='ISO8601').dt.hour

    # Reproject the data to EPSG 31982
    final_geo_data = final_geo_data.to_crs(epsg=31982)

    final_geo_data['timestamp'] = final_geo_data['timestamp'].astype(str)
    final_geo_data['day'] = final_geo_data['day'].astype(str)
    final_geo_data['hour'] = final_geo_data['hour'].astype(int)
    final_geo_data.to_file(
        f"{savepath}/final_geo_data.geojson", driver="GeoJSON")

# %%
def process_data(base_day, gridpath, current_hour, escala, savepath):
    final_geo_data = gpd.read_file(
        f'{savepath}/final_geo_data.geojson', crs='EPSG:31982')

    base_day_date = datetime.strptime(base_day, '%Y-%m-%d').date()

    # Load the grid
    grid = gpd.read_file(gridpath)

    # Include the desired columns from the grid
    grid_with_desired_columns = grid[[
        'index', 'nome', 'tipo', 'x', 'y', 'geometry']]

    # Perform the spatial join to get the grid cell index for each row in final_geo_data
    final_geo_data_with_index = gpd.sjoin(final_geo_data, grid_with_desired_columns[[
                                          'index', 'geometry']], how='inner', predicate='intersects')

    # Group by index, day, and hour to get the mean speedKMH for each combination
    grouped_data = final_geo_data_with_index.groupby(
        ['index', 'day', 'hour']).agg({'speedKMH': 'mean'}).reset_index()

    # Create a multi-index that contains every combination of index, day, and hour
    multi_index = pd.MultiIndex.from_product([grouped_data['index'].unique(
    ), grouped_data['day'].unique(), range(24)], names=['index', 'day', 'hour'])

    # Reindex the grouped data with the new multi-index
    grouped_data_reindexed = grouped_data.set_index(
        ['index', 'day', 'hour']).reindex(multi_index)

    # Fill missing values with 40 km/h
    grouped_data_reindexed['speedKMH'].fillna(40, inplace=True)
    grouped_data_reindexed = grouped_data_reindexed.reset_index()

    # Create a column for the combined day and hour
    grouped_data_reindexed['day_hour'] = grouped_data_reindexed['day'].astype(
        str) + "_" + grouped_data_reindexed['hour'].astype(str)
    pivot_data = grouped_data_reindexed.pivot(
        index='index', columns='day_hour', values='speedKMH')

    # Remove rows with all null values
    pivot_data_cleaned = pivot_data.dropna(how='all')

    # Determine the previous week's equivalent day
    previous_week_date = base_day_date - timedelta(days=7)

    # Determine the latest whole hour based on the current time
    # current_hour = datetime.now().hour - 1

    # Filter out the data for the base_day and previous_week_date
    current_week_hour_data = pivot_data_cleaned.filter(like=str(base_day_date))
    previous_week_hour_data = pivot_data_cleaned.filter(
        like=str(previous_week_date))

    # Extract the data for the current_hour
    latest_hour_column_current_week = str(
        base_day_date) + "_" + str(current_hour)
    latest_hour_column_previous_week = str(
        previous_week_date) + "_" + str(current_hour)
    if latest_hour_column_current_week in current_week_hour_data.columns:
        current_week_hour_data_filtered = current_week_hour_data[[
            latest_hour_column_current_week]]
        current_week_hour_data_filtered = current_week_hour_data_filtered[
            current_week_hour_data_filtered[latest_hour_column_current_week] <= 35]
        if not current_week_hour_data_filtered.empty:
            current_week_hour_data_filtered.rename(
                columns={latest_hour_column_current_week: 'speedkph'}, inplace=True)
            bins = [0, 10, 15, 20, 25, 30, 35]
            labels = ['0-10', '11-15', '16-20', '21-25', '26-30', '31-35']
            current_week_hour_data_filtered['class'] = pd.cut(
                current_week_hour_data_filtered['speedkph'], bins=bins, labels=labels, right=True, include_lowest=True).astype(str)
            merged_data_current_week = grid_with_desired_columns.merge(
                current_week_hour_data_filtered, left_on='index', right_index=True)[['geometry', 'speedkph', 'class']]
            gdf_merged_current_week = gpd.GeoDataFrame(
                merged_data_current_week, geometry='geometry')
            gdf_merged_current_week.to_crs(epsg=4326).to_file(
                f"{savepath}/{escala}_latest_hour_data_current_week.geojson", driver='GeoJSON')

#    if latest_hour_column_previous_week in previous_week_hour_data.columns:
#        previous_week_hour_data_filtered = previous_week_hour_data[[
#            latest_hour_column_previous_week]]
#        previous_week_hour_data_filtered = previous_week_hour_data_filtered[
#            previous_week_hour_data_filtered[latest_hour_column_previous_week] <= 35]
#        if not previous_week_hour_data_filtered.empty:
#            previous_week_hour_data_filtered.rename(
#                columns={latest_hour_column_previous_week: 'speedkph'}, inplace=True)
#            bins = [0, 10, 15, 20, 25, 30, 35]
#            labels = ['0-10', '11-15', '16-20', '21-25', '26-30', '31-35']
#            previous_week_hour_data_filtered['class'] = pd.cut(
#                previous_week_hour_data_filtered['speedkph'], bins=bins, labels=labels, right=True, include_lowest=True).astype(str)
#            merged_data_previous_week = grid_with_desired_columns.merge(
#                previous_week_hour_data_filtered, left_on='index', right_index=True)[['geometry', 'speedkph', 'class']]
#            gdf_merged_previous_week = gpd.GeoDataFrame(
#                merged_data_previous_week, geometry='geometry')
#            gdf_merged_previous_week.to_crs(epsg=4326).to_file(
#                f"{savepath}/{escala}_latest_hour_data_previous_week.geojson", driver='GeoJSON')

# %%
def gerar_tabelas(base_day, savepath):
    final_geo_data = gpd.read_file(
        f'{savepath}/final_geo_data.geojson', crs='EPSG:31982')
    dados_tabelas = final_geo_data[['day', 'hour', 'delay', 'dia_semana']]

    day_map = {
        'Monday': 'Segunda-Feira',
        'Tuesday': 'Terça-Feira',
        'Wednesday': 'Quarta-Feira',
        'Thursday': 'Quinta-Feira',
        'Friday': 'Sexta-Feira',
        'Saturday': 'Sábado',
        'Sunday': 'Domingo'
    }

    base_day_weekday = pd.to_datetime(base_day).day_name()
    base_day_weekday_pt = day_map.get(base_day_weekday, base_day_weekday)

    # Filtrar os

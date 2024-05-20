# %%
# dados feed
import os
import json
import datetime
import urllib.request
#from shapely.geometry import LineString

# Checagem e criação de diretórios
resultados = 'resultados'
os.makedirs(resultados, exist_ok=True)

# %%
dia_semana_t = ('Segunda-Feira', 'Terça-Feira', 'Quarta-Feira',
                'Quinta-Feira', 'Sexta-Feira', 'Sábado', 'Domingo')

feed_url = 'https://www.waze.com/row-partnerhub-api/partners... << colocar o link do seu feed'

# %%
#dados_coletados = []

try:
    response = urllib.request.urlopen(feed_url)
    dados_coletados = [json.loads(response.read())]
except Exception as e:
    print(f'Erro ao obter dados do feed: {e}')
    dados_coletados = []

# %%
group_alerts = {}
group_irregularities = {}
group_jams = {}


def adicionar_alerta(ee):

    data_utc = datetime.datetime.fromtimestamp(
        float(ee['pubMillis'])/1000.)
    data_alerta = data_utc.strftime('%Y-%m-%d')

    if data_alerta not in group_alerts:
        group_alerts[data_alerta] = {
            'type': 'FeatureCollection',
            'uuids': [],
            'features': []
        }

    if ee['uuid'] not in group_alerts[data_alerta]['uuids']:
        unidade = {
            'type': 'Feature',
            'geometry': {
                'type': 'Point',
                'coordinates': [ee['location']['x'], ee['location']['y']],
            },
            'properties': {k: ee[k] for k in ee.keys() - {'location'}}
        }
        unidade['properties']['timestamp'] = data_utc
        unidade['properties']['dia_semana'] = dia_semana_t[data_utc.weekday()]

        group_alerts[data_alerta]['features'].append(unidade)
        group_alerts[data_alerta]['uuids'].append(ee['uuid'])


def adicionar_irregularidade(ee):

    data_utc = datetime.datetime.fromtimestamp(
        float(ee['updateDateMillis'])/1000.)
    data_irregularidade = data_utc.strftime('%Y-%m-%d')

    if data_irregularidade not in group_irregularities:
        group_irregularities[data_irregularidade] = {
            'type': 'FeatureCollection',
            'ids': [],
            'features': []
        }

    if ee['id'] not in group_irregularities[data_irregularidade]['ids']:
        unidade = {
            'type': 'Feature',
            'geometry': {
                'type': 'LineString',
                'coordinates': [[pts['x'], pts['y']] for pts in ee['line']],
            },
            'properties': {k: ee[k] for k in ee.keys() - {'line', 'alerts'}}
        }

        longdif = ee['line'][0]['x'] - ee['line'][-1]['x']
        latdif = ee['line'][0]['y'] - ee['line'][-1]['y']
        if abs(longdif) > abs(latdif):
            unidade['properties']['orientacao'] = 'LO' if longdif > 0 else 'OL'
        else:
            unidade['properties']['orientacao'] = 'NS' if latdif > 0 else 'SN'

        unidade['properties']['alerts'] = [alertas['uuid'] for alertas in ee['alerts']]
        for alertas in ee['alerts']:
            adicionar_alerta(alertas)

        unidade['properties']['timestamp'] = data_utc
        unidade['properties']['dia_semana'] = dia_semana_t[data_utc.weekday()]

        group_irregularities[data_irregularidade]['ids'].append(ee['id'])
        group_irregularities[data_irregularidade]['features'].append(unidade)


def adicionar_congestionamento(ee):

    data_utc = datetime.datetime.fromtimestamp(
        float(ee['pubMillis'])/1000.)
    data_congestionamento = data_utc.strftime('%Y-%m-%d')

    if data_congestionamento not in group_jams:
        group_jams[data_congestionamento] = {
            'type': 'FeatureCollection',
            'uuids': [],
            'features': []
        }

    if ee['uuid'] not in group_jams[data_congestionamento]['uuids']:
        unidade = {
            'type': 'Feature',
            'geometry': {
                'type': 'LineString',
                'coordinates': [[pts['x'], pts['y']] for pts in ee['line']],
            },
            'properties': {k: ee[k] for k in ee.keys() - {'line'}}
        }

        longdif = ee['line'][0]['x'] - ee['line'][-1]['x']
        latdif = ee['line'][0]['y'] - ee['line'][-1]['y']
        if abs(longdif) > abs(latdif):
            unidade['properties']['orientacao'] = 'LO' if longdif > 0 else 'OL'
        else:
            unidade['properties']['orientacao'] = 'NS' if latdif > 0 else 'SN'

        unidade['properties']['timestamp'] = data_utc
        unidade['properties']['dia_semana'] = dia_semana_t[data_utc.weekday()]

        group_jams[data_congestionamento]['uuids'].append(ee['uuid'])
        group_jams[data_congestionamento]['features'].append(unidade)


for e in dados_coletados:
    # alertas
    try:
        for ee in e['alerts']:
            adicionar_alerta(ee)
    except KeyError:
        print('sem alertas')

    # irregularidades
    try:
        for ee in e['irregularities']:
            adicionar_irregularidade(ee)
    except KeyError:
        print('sem irregularidades')

    # congestionamentos
    try:
        for ee in e['jams']:
            adicionar_congestionamento(ee)
    except KeyError:
        print('sem congestionamentos')

# %%


def atualiza_arquivo(grupo, dados, id):
    file_path = f'{resultados}/{dados[0][0:4]}/{grupo}/{dados[0]}_{grupo}.json'
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    try:
        with open(file_path, 'r', encoding='UTF-8') as arq_json:
            data = json.load(arq_json)
            diferencas = set(data[f'{id}s']) ^ set(dados[1][f'{id}s'])
            if len(diferencas) == 0:
                print('registro existente')
            else:
                for uiiddif in diferencas:
                    for novo_registro in dados[1]['features']:
                        if novo_registro['properties'][id] == uiiddif:
                            print('atualizando registro')
                            data['features'].append(novo_registro)
                            data[f'{id}s'].append(novo_registro['properties'][id])
        with open(file_path, 'w', encoding='UTF-8') as fp:
            json.dump(data, fp, default=str, indent=4)
    except FileNotFoundError:
        with open(file_path, 'w', encoding='UTF-8') as fp:
            json.dump(dados[1], fp, default=str, indent=4)


# %%
for arquivo_final in group_alerts.items():
    atualiza_arquivo('alerts', arquivo_final, 'uuid')

for arquivo_final in group_irregularities.items():
    atualiza_arquivo('irregularities', arquivo_final, 'id')

for arquivo_final in group_jams.items():
    atualiza_arquivo('jams', arquivo_final, 'uuid')

# %%

# %%
# month/type selection

# %%
import datetime
from calendar import monthrange
import pandas as pd
import geopandas as gpd
pd.set_option('display.max_columns', 40)

# %%
# config
local_dados = '/geo/www/mapas/waze/resultados'
data_hj = datetime.date.today()
hoje = data_hj.strftime('%Y-%m-%d')
num_mesatual = int(data_hj.strftime('%m'))
num_anoatual = int(data_hj.strftime('%Y'))
data_mes_passado = data_hj.replace(day=1) - datetime.timedelta(days=1)
num_mespassado = int(data_mes_passado.strftime('%m'))
num_anopassado = int(data_mes_passado.strftime('%Y'))

# %%

# pegar dados mês/tipo


def pegar_mes(ano, mes, tipo):
    dias_mes = range(monthrange(ano, mes)[1]+1)[1:]
    dias = []
    for d in dias_mes:
        dias.append(f'{ano}-{mes:02}-{d:02}_{tipo}')

    dados_mes = []
    for f in dias:
        try:
            dados_mes.append(gpd.read_file(
                f'{local_dados}/{ano}/{tipo}/{f}.json'))
        except:
            print(f'dia {f} não encontrado')
    return gpd.GeoDataFrame(pd.concat(dados_mes, ignore_index=True),
                            crs=dados_mes[0].crs)

# %%
# ### Acumulados intervalos de tempo de espera por zonas, data atual/anterior:
# dia, semana e mês.
#
#
# ### Listas maior tempo de espera:
# vias/sentido e zona/sentido.
#
# ### Mapa
# seta direção, espessura e cor da linha tempo de espera.


# %%
mes_atual_jams = pegar_mes(num_anoatual, num_mesatual, 'jams')
mes_passado_jams = pegar_mes(num_anopassado, num_mespassado, 'jams')

# %%
# zonas
regioes_itj = gpd.read_file('basedata/regs.shp')

# %%
# união zonas
mes_atual_jams = gpd.overlay(
    mes_atual_jams,
    regioes_itj,
    how='intersection')

mes_passado_jams = gpd.overlay(
    mes_passado_jams,
    regioes_itj,
    how='intersection')

# %%
# dias
mes_atual_jams_dias = mes_atual_jams.groupby(["clust","category"])["id"].count().unstack()
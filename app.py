from flask import Flask, render_template, request, redirect
import numpy as np
import requests
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import datetime as dt
from waitress import serve
app = Flask(__name__)
#conversion functions for salary
conversion_rates = {'USD': 90,'EUR': 110,'KZT': 0.20}

def convert_to_rur(value, currency):
    if value is None or currency == 'RUR':
        return value
    return value * conversion_rates.get(currency, 1) 

def process_salary(salary_data):
    from_value = salary_data.get('from')
    to_value = salary_data.get('to')
    from_value = convert_to_rur(from_value, salary_data['currency'])
    to_value = convert_to_rur(to_value, salary_data['currency'])
    return {
        'from': from_value,
        'to': to_value,
        'currency': 'RUR',
        'gross': salary_data['gross']
    }
def calculate_single_number(data_dict):
    if data_dict is not None:
        from_value = data_dict.get('from')
        to_value = data_dict.get('to')

        if from_value is None and to_value is None:
            return None
        elif from_value is not None and to_value is not None:
            return (from_value + to_value) / 2
        elif from_value is not None:
            return from_value
        else:
            return to_value
#Очистка городов, работодателей, URL
def get_city(area):
	city=area.get('name')
	return city
	
def get_employer(employer):
	name=employer.get('name')
	return name
	
def clean_url(hh_url):
	url='https://spb.hh.ru/vacancy/'
	for i in hh_url:
		if i.isdigit():
			url+=str(i)
	return url
def get_vac_id(hh_url):
	vac_id=''
	for i in hh_url:
		if i.isdigit():
			vac_id+=str(i)
	vac_id=int(vac_id)
	return vac_id
def get_stats(df):
	stats={
	'Средняя ЗП':round(df.describe()['salary_gross_RUR']['mean']),
	'25 перцентиль':round(df.describe()['salary_gross_RUR']['25%']),
	'50 перцентиль (медиана)':round(df.describe()['salary_gross_RUR']['50%']),
	'75 перцентиль':round(df.describe()['salary_gross_RUR']['75%']),
	'90 перцентиль':round(np.percentile(df['salary_gross_RUR'],90)),
	'Максимум':round(df.describe()['salary_gross_RUR']['max'])
	}
	return stats
global banned_id_list
banned_id_list=[]
#Получение вакансий
@app.route('/',methods=['GET', 'POST'])
def get_vacancies():
	if request.method == 'POST':
		global text
		text=request.form['vacancy']
		banned_id_list=[]
	else:
		return render_template('index.html')
	try:
		target_url='https://api.hh.ru/vacancies?text='+text
		r = requests.get(target_url,params={'only_with_salary':'true'}).json() 
		p=r['pages'] 
		#требуемые поля выгрузки
		vac = {'id':[],'name':[],'area':[],'salary':[],'address':[],'url':[],'employer':[],'snippet':[]}
		for i in range(0, p):
			page_content=requests.get(target_url, params={'page': i, 'per_page':20}).json()
			page_content_items=page_content['items']
			for j in range(0,len(page_content_items)):
				for k in vac.keys():
					vac[k].append(page_content_items[j].get(k))
		global df
		df=pd.DataFrame.from_dict(vac, orient='columns')
		#Очищаем названия городов,работодателей, URL
		df['area']=df['area'].apply(get_city)
		df['employer']=df['employer'].apply(get_employer)
		df['url']=df['url'].apply(clean_url)
		df['vac_id']=df['url'].apply(get_vac_id)
		#Фильтруем вакансии по зп и обрабатываем их
		df = df[df['salary'].notna()].reset_index(drop=True)
		df['salary_RUR']=df['salary'].apply(process_salary)
		df['single_number_RUR']= df['salary_RUR'].apply(calculate_single_number)
		df.loc[df['salary_RUR'].apply(lambda x: not x['gross']), 'single_number_RUR'] /= 0.87
		df['salary_gross_RUR']=df['single_number_RUR'].apply(round)
		df=df[['vac_id','name','area','url','employer','salary_gross_RUR']].reset_index(drop=True)
		stats=get_stats(df)
		#Гистограмма
		plt.clf()
		plt.hist(df['salary_gross_RUR'])
		plt.title("Распределение ЗП по позиции "+text)
		global hist_img_path
		hist_img_path="static/images/last_salary_hist.png"
		plt.savefig(hist_img_path)
		return render_template('results.html',vacancies_table=df,req=request.form['vacancy'],hist_img_path=hist_img_path,stats=stats)

	except Exception:
		import traceback
		return render_template('index.html',err='Ошибка при загрузке'+str(traceback.format_exc())+'\n Вот что отдало API:'+str(page_content)[0:200])

@app.route("/<int:v_id>",methods=['GET', 'POST'])
def delete_row(v_id):
	banned_id_list.append(v_id)
	vacancies_filtered=df[~df.vac_id.isin(banned_id_list)]
	plt.clf()
	plt.hist(vacancies_filtered['salary_gross_RUR'])
	plt.title("Распределение ЗП по позиции "+text)
	plt.savefig(hist_img_path)
	stats=get_stats(vacancies_filtered)
	return render_template('results.html',vacancies_table=vacancies_filtered,req=text,hist_img_path=hist_img_path,stats=stats)

@app.route("/clear/",methods=['GET', 'POST'])
def clear():
	return render_template('index.html')	
	
if __name__=='__main__':
	serve(app, host="0.0.0.0", port=8000)
	#app.run(port=8000,debug=True)
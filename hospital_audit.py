from palettable.cartocolors.sequential import Teal_5
import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd
import numpy as np
import datetime
import re
import os
os.chdir('Settings of Care Audit')
#read in data.
audit_df = pd.read_excel('Setting of Care Audit.xlsx')
audit_df.columns = [col.strip() for col in audit_df.columns]

#Map wards onto their care group
ward_mapper = pd.read_excel('WardCodes.xlsx')
audit_df['Ward'] = [ward.strip() for ward in audit_df['Ward']]
audit_df['Ward first word'] = [ward.replace(u'\xa0', u' ').split(' ')[0] for ward in audit_df['Ward']]
ward_mapper['Ward'] = [ward.replace(u'\xa0', u' ').split(' ')[0] for ward in ward_mapper['Ward']]
audit_df = ward_mapper.merge(audit_df, left_on='Ward', right_on='Ward first word', how='right', suffixes=['_x', None])
audit_df = audit_df.drop(['Ward_x', 'Ward first word'], axis=1)

#Clean up where an outlier patient should be using mapper
outlier_mapper = pd.read_excel('outlier lookup.xlsx')
outlier_mapper.columns = [col.strip() for col in outlier_mapper.columns]
audit_df['If yes, which team should the patient be under?'] = audit_df['If yes, which team should the patient be under?'].str.lower()
audit_df = audit_df.merge(outlier_mapper, on='If yes, which team should the patient be under?', how='left')

#Clean columns and create additional columns
audit_df['Date'] = audit_df['Completion time'].dt.date
audit_df['length of stay'] = (audit_df['Completion time'] - audit_df['Date of Admission']).dt.days
audit_df['21+ Days'] = np.where(audit_df['Length of Stay'] == '21+ Days', 1, 0)
audit_df['Med-fit for discharge'] = np.where(audit_df['Is the patient medically fit for discharge?'] == 'Yes', 1, 0)
audit_df['Medical Outlier'] = np.where(audit_df['Is the patient an outlier?'] == 'Yes', 1, 0)

#Clean age column.
age_col = []
for age in audit_df['Age'].astype(str):
    try:
        if ('year' in age) or ('y' in age):
            #remove additional string/months in age section.
            age = re.search(r'\d+', age).group()
        elif ('month' in age) or ('day' in age):
            #babies under 1 are classed as 0.
            age = 0
        age_col.append(int(age))
    except:
        age_col.append(np.nan)
audit_df['Cleaned Age'] = age_col


def aggregate_data(input_df, aggregation_column=None, pivot=False):
    #If additional groupings, add here.
    groupby_cols = ['Date', aggregation_column] if aggregation_column else 'Date'
    #Get the summary data across the hospital each day.
    df = (input_df.groupby(groupby_cols)
          .agg(number_of_patients=('Patient Name/Initials', 'count'),
               average_patient_age=('Cleaned Age', 'mean'),
               maximum_stay_days=('length of stay', 'max'),
               average_stay_days=('length of stay', 'mean'),
               number_over_21_days=('21+ Days', 'sum'),
               number_outlier=('Medical Outlier', 'sum'),
               number_medfit_for_dis=('Med-fit for discharge', 'sum')))
    #round columns
    df['average_patient_age'] = df['average_patient_age'].round(0)
    df['average_stay_days'] = df['average_stay_days'].round(2)
    #add % of patients staying longer than 21 days
    df['%_over_21_days'] = ((df['number_over_21_days'] / df['number_of_patients']) * 100).round(2).astype(str) + '%'
    df['%_outliers'] = ((df['number_outlier'] / df['number_of_patients']) * 100).round(2).astype(str) + '%'
    df['%_medfit_for_dis'] = ((df['number_medfit_for_dis'] / df['number_of_patients']) * 100).round(2).astype(str) + '%'
    #remove _ from column names
    df.columns = [col.replace('_', ' ') for col in df.columns]
    #If the table needs pivoting to look cleaner, do it here.
    if pivot:
        df = df.reset_index().pivot(index=aggregation_column, columns='Date')
    #Return table
    return df

#Run function for different groupings.
df_by_day = aggregate_data(audit_df)
df_by_ward = aggregate_data(audit_df, 'Ward', True)
df_by_care_group = aggregate_data(audit_df, 'CareGroup', True)
df_by_local_authority = aggregate_data(audit_df, 'Local Authority', True)

#How many are being cared for in the wrong setting, and where should they be.
patients_in_wrong_setting = (audit_df.loc[audit_df['Are they being cared for in the right setting?'] == 'No']
                             .groupby(['Date', 'If no - what is the appropriate care setting'], as_index=False)['Patient Name/Initials'].count()
                             .pivot(index='If no - what is the appropriate care setting', columns='Date', values='Patient Name/Initials')
                             .sort_values(by=datetime.date(2024, 4, 22), ascending=False))

#export to Excel.
with pd.ExcelWriter("aggregated_audit_figures.xlsx") as writer:
    df_by_day.to_excel(writer, sheet_name="Total")
    df_by_care_group.to_excel(writer, sheet_name="Care Group")
    df_by_ward.to_excel(writer, sheet_name="Ward")
    df_by_local_authority.to_excel(writer, sheet_name="Local Authority")
    patients_in_wrong_setting.to_excel(writer, sheet_name='Care Setting')

        ####PLOTS####
    
    #Top level plots
#Total number of patients
df_by_day['number of patients'].plot(kind='bar', title='Number of patients per day', xlabel='Date', ylabel='Number of patients', rot=0)
plt.savefig('Number of patients by day.png', bbox_inches='tight')
#Maximum length of stay
df_by_day['maximum stay days'].plot(kind='bar', title='Maximum length of stay per day', xlabel='Date', ylabel='Days since admission', rot=0)
plt.savefig('Maximum stay by day.png', bbox_inches='tight')
#Average length of stay
df_by_day['average stay days'].plot(kind='bar', title='Average length of stay per day', xlabel='Date', ylabel='Average days since admission', rot=0)
plt.savefig('Average stay by day.png', bbox_inches='tight')
#Other summaries
df_by_day[['number medfit for dis', 'number over 21 days', 'number outlier']].plot(kind='bar', xlabel='Date', ylabel='Number of patients', rot=0)
plt.savefig('Summary by day.png', bbox_inches='tight')


    #Care Group Plots
#Number of patients by caregroup by day
(df_by_care_group['number of patients'].sort_values(by=datetime.date(2024, 4, 22), ascending=False)
 .plot(kind='bar', figsize=(20,15), title='Number of Patients by Care Group', xlabel='Date', ylabel='Number of patients', rot=0, colormap=Teal_5.mpl_colormap))
plt.savefig('Number of Patients by care group.png', bbox_inches='tight')
#Average length of stay by caregroup by day
(df_by_care_group['average stay days'].sort_values(by=datetime.date(2024, 4, 22), ascending=False)
 .plot(kind='bar', figsize=(20,15), title='Average length of stay by care group', xlabel='Date', ylabel='Average number of days', rot=0, colormap=Teal_5.mpl_colormap))
plt.savefig('Average length of stay by care group.png', bbox_inches='tight')
#% medfit for discharge by caregroup by day
(df_by_care_group['% medfit for dis'].replace({'%':''}, regex=True).astype('float').sort_values(by=datetime.date(2024, 4, 22), ascending=False)
 .plot(kind='bar', figsize=(20,15), title='% of patients medically fit for discharge by care group', xlabel='Date', ylabel='% of patients', rot=0, colormap=Teal_5.mpl_colormap))
plt.savefig('% medfit for dis by care group.png', bbox_inches='tight')


    #Local Authority Plots
#% Medfit for Discharge
(df_by_local_authority['% medfit for dis'].replace({'%':''}, regex=True).astype('float').sort_values(by=datetime.date(2024, 4, 22), ascending=False)
 .plot(kind='bar', figsize=(20,15), title='% of patients medically fit for discharge by local authority', xlabel='Date', ylabel='% of patients', rot=0, colormap=Teal_5.mpl_colormap))
plt.savefig('% medfit for dis by local authority.png', bbox_inches='tight')


    #Appropriate care setting plots
#Plot of number of patients in the wrong care setting and where they should be.
patients_in_wrong_setting.plot(kind='bar', figsize=(20,15), title='Where is the approriate care setting?', xlabel='Setting', ylabel='Number of patients',
                               rot=35, colormap=Teal_5.mpl_colormap)
plt.savefig('Appropriate care setting by day.png', bbox_inches='tight')


    #Outlier plots
#Plot of where outliers are overall
overall_outlier_patients = audit_df.groupby('Speciality', as_index=True)['Medical Outlier'].count()
filtered = overall_outlier_patients.loc[overall_outlier_patients > 5].sort_values(ascending=False)
filtered.plot(kind='bar', figsize=(20,15), title='Where outlier patients are', legend=False, xlabel='Specialty', ylabel='Number of Patients', rot=90, fontsize=14)
plt.savefig('Where outlier patients are.png',  bbox_inches='tight')
#Plot of where outliers should be overall
overall_outliers_should_be = audit_df.groupby('Outlier - Where should the patient be?', as_index=True)['Medical Outlier'].count()
filtered = overall_outliers_should_be.loc[overall_outliers_should_be > 1].sort_values(ascending=False)
filtered.plot(kind='bar', figsize=(20,15), title='Where outlier patients should be', legend=False, xlabel='Location', ylabel='Number of Patients', rot=90)
plt.savefig('Where outlier should be.png',  bbox_inches='tight')

#Lookup plots of where outliers are vs where they should be
outlier_pairs = audit_df[['Speciality', 'Outlier - Where should the patient be?']].dropna().value_counts().reset_index(name='count')
#Lookup table/heatmap of all pairs
outlier_lookup = (outlier_pairs#.loc[outlier_pairs['count'] > 4]
                  .pivot(index='Speciality', columns='Outlier - Where should the patient be?', values='count').sort_values(by='Speciality'))
fig, ax = plt.subplots(figsize=(25,10))
sns.heatmap(outlier_lookup, cmap='RdYlGn_r', robust=True, annot=True, fmt='g', linewidths=0.5, linecolor='k',  square=True, xticklabels=outlier_lookup.columns, ax=ax)
ax.set(xlabel='Where outlier patient should be', ylabel='Where outlier patient is')
plt.title('Outlier Patient Lookup Table')
plt.savefig('Outlier patient lookup table.png', bbox_inches='tight')
#Lookup table/heatmap of pairs that occur 5 or more times
outlier_lookup_signif = (outlier_pairs.loc[outlier_pairs['count'] >= 5].copy()
                  .pivot(index='Speciality', columns='Outlier - Where should the patient be?', values='count').sort_values(by='Speciality'))
fig, ax = plt.subplots()
sns.heatmap(outlier_lookup_signif, cmap='RdYlGn_r', robust=True, annot=True, fmt='g', linewidths=0.5, linecolor='k',  square=True, ax=ax)
ax.set(xlabel='Where outlier patient should be', ylabel='Where outlier patient is')
plt.title('Outlier Patient Lookup Table where More Than 5 Patients')
plt.savefig('Outlier patient lookup table gt 5.png', bbox_inches='tight')
#Lookup table/heatmap of pairs that aren't direct matches
outlier_lookup_notsame = (outlier_pairs.loc[outlier_pairs['Speciality'] != outlier_pairs['Outlier - Where should the patient be?']].copy()
                          .pivot(index='Speciality', columns='Outlier - Where should the patient be?', values='count').sort_values(by='Speciality'))
fig, ax = plt.subplots(figsize=(25,10))
sns.heatmap(outlier_lookup_notsame, cmap='RdYlGn_r', robust=True, annot=True, fmt='g', linewidths=0.5, linecolor='k',  square=True, ax=ax)
ax.set(xlabel='Where outlier patient should be', ylabel='Where outlier patient is')
plt.title('Outlier Patient Lookup Table where Not the Same Location')
plt.savefig('Outlier patient lookup table not same.png', bbox_inches='tight')
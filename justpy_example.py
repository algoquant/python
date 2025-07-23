# Produces error:
# ImportError: cannot import name 'ParamSpec' from 'typing_extensions'

import justpy as jp
import pandas as pd


wm = pd.read_csv('https://elimintz.github.io/women_majors.csv').round(2)
# Create list of majors which start under 20% women students
wm_under_20 = list(wm.loc[0, wm.loc[0] < 20].index)

fig = wm.jp.plot(0, wm_under_20, kind='spline', title='The gender gap is transitory - even for extreme cases',
               subtitle='Percentage of Bachelors conferred to women form 1970 to 2011 in the US for extreme cases where the percentage was less than 20% in 1970',
                classes='m-2 p-2 w-3/4')
print(fig)


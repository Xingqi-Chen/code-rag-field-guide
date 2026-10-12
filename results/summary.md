# 可复算检索结果

仅26个正例进入均值；4个负例见原始结果。下表由 `python3 scripts/aggregate.py` 自动生成。

|预算|方法|Recall|MRR|nDCG|证据覆盖|全部证据命中|未标注块比例|平均token|平均阶段合计ms|
|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|
|4|bm25|0.413|0.481|0.381|0.394|0.192|0.788|633.4|0.35|
|4|dense|0.558|0.561|0.486|0.554|0.346|0.731|649.0|3.00|
|4|graph|0.574|0.535|0.486|0.564|0.462|0.721|676.1|3.52|
|4|hybrid|0.551|0.548|0.472|0.535|0.346|0.731|656.7|3.48|
|4|random|0.346|0.500|0.352|0.321|0.115|0.837|579.0|3.56|
|8|bm25|0.561|0.503|0.452|0.545|0.346|0.846|1289.4|0.35|
|8|dense|0.731|0.581|0.568|0.740|0.577|0.812|1313.6|3.00|
|8|graph|0.635|0.556|0.515|0.625|0.462|0.837|1357.4|3.52|
|8|hybrid|0.679|0.568|0.532|0.673|0.462|0.822|1379.5|3.48|
|8|random|0.551|0.548|0.472|0.535|0.346|0.865|1117.6|3.56|
|12|bm25|0.593|0.503|0.464|0.583|0.385|0.891|1904.3|0.35|
|12|dense|0.782|0.584|0.588|0.788|0.615|0.862|1962.0|3.00|
|12|graph|0.753|0.565|0.560|0.744|0.615|0.865|2035.2|3.53|
|12|hybrid|0.702|0.568|0.542|0.696|0.538|0.875|2020.6|3.48|
|12|random|0.606|0.562|0.500|0.593|0.346|0.897|1810.5|3.58|

## 主预算分组证据覆盖

|范围|方法|题数|覆盖率|
|---|---|---:|---:|
|category:concept|bm25|4|0.500|
|category:concept|dense|4|0.875|
|category:concept|graph|4|0.625|
|category:concept|hybrid|4|0.625|
|category:concept|random|4|0.500|
|category:cross_file|bm25|8|0.500|
|category:cross_file|dense|8|0.594|
|category:cross_file|graph|8|0.438|
|category:cross_file|hybrid|8|0.594|
|category:cross_file|random|8|0.375|
|category:impact|bm25|6|0.611|
|category:impact|dense|6|0.917|
|category:impact|graph|6|0.792|
|category:impact|hybrid|6|0.792|
|category:impact|random|6|0.653|
|category:location|bm25|8|0.562|
|category:location|dense|8|0.688|
|category:location|graph|8|0.688|
|category:location|hybrid|8|0.688|
|category:location|random|8|0.625|
|repo:click|bm25|13|0.577|
|repo:click|dense|13|0.712|
|repo:click|graph|13|0.519|
|repo:click|hybrid|13|0.577|
|repo:click|random|13|0.481|
|repo:requests|bm25|13|0.513|
|repo:requests|dense|13|0.769|
|repo:requests|graph|13|0.731|
|repo:requests|hybrid|13|0.769|
|repo:requests|random|13|0.590|

图减hybrid，平均差 -0.0481；配对bootstrap描述区间 [-0.10576923076923077, 0.0]；胜/平/负 0/23/3。此区间不代表随机抽样总体。

## 逐题图与混合检索比较

|题目|类型|Hybrid覆盖|Graph覆盖|差值|
|---|---|---:|---:|---:|
|C01|location|0.000|0.000|+0.000|
|C02|location|1.000|1.000|+0.000|
|C03|location|1.000|1.000|+0.000|
|C04|location|0.000|0.000|+0.000|
|C05|cross_file|0.000|0.000|+0.000|
|C06|cross_file|0.500|0.000|-0.500|
|C07|cross_file|0.500|0.250|-0.250|
|C08|cross_file|1.000|1.000|+0.000|
|C09|impact|1.000|1.000|+0.000|
|C10|impact|0.333|0.333|+0.000|
|C11|impact|0.667|0.667|+0.000|
|C12|concept|1.000|1.000|+0.000|
|C13|concept|0.500|0.500|+0.000|
|R01|location|1.000|1.000|+0.000|
|R02|location|1.000|1.000|+0.000|
|R03|location|0.500|0.500|+0.000|
|R04|location|1.000|1.000|+0.000|
|R05|cross_file|0.250|0.250|+0.000|
|R06|cross_file|1.000|1.000|+0.000|
|R07|cross_file|0.500|0.000|-0.500|
|R08|cross_file|1.000|1.000|+0.000|
|R09|impact|1.000|1.000|+0.000|
|R10|impact|0.750|0.750|+0.000|
|R11|impact|1.000|1.000|+0.000|
|R12|concept|0.500|0.500|+0.000|
|R13|concept|0.500|0.500|+0.000|

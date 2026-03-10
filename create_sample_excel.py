import pandas as pd
import os

data = {
    "URL": [
        "https://www.pipelagging.com/pipe-insulation/rockwool-rocklap-1m-foil-backed-pipe-insulation-lagging",
        "https://www.pipelagging.com/pipe-insulation/rockwool-rocklap-1m-foil-backed-pipe-insulation-lagging",
        "https://www.pipelagging.com/pipe-insulation/armaflex-self-seal-pipe-insulation-lagging-black-nitrile-foam-class-o-2m"
    ],
    "Description": [
        "15 x 25mm H&V Lag Foil Covered",
        "22 x 25mm H&V Lag Foil Covered",
        "28mm x 19mm Armaflex"
    ],
    "comments": [
        None,
        None,
        None
    ]
}

df = pd.DataFrame(data)
df.to_excel("input_urls.xlsx", index=False)
print("Created input_urls.xlsx")

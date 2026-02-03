import pandas as pd
import asyncio

from utils.dataset import capture_screenshots_async

data = pd.read_excel("./data/Price_Normalization_Dataset.xlsx")

async def main():
    dataset = await capture_screenshots_async(data)
    dataset.to_excel("./data/Price_Normalization_Dataset_with_images.xlsx", index=False)

if __name__ == "__main__":
    asyncio.run(main())

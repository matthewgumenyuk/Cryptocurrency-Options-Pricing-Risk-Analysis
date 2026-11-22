
from datetime import datetime
import streamlit as st
import pandas as pd
import aiohttp
import asyncio
import requests
import json
import math
import time
import scipy.stats as stats
import QuantLib as ql
import plotly.express as px
import plotly.graph_objects as graph
import numpy as np
from scipy.interpolate import griddata
from sklearn.neighbors import LocalOutlierFactor
# python -m streamlit run "C:\Users\gumen\OneDrive\Desktop\Options.py"
'''
Bitcoin Option Analysis
'''

global market_prices
global BitcoinMarketPrice
global RiskFreeRate
global GabagoolCollections
global my_bar
global InstrumentsToPlay
global SaleTimes
global StartTimeOfCalls

RiskFreeRateByDaysTillMaturity = {
    28: 0.0,
    42: 0.0,
    56: 0.0,
    91: 0.0,
    119: 0.0,
    182: 0.0,
    364: 0.0,
}

async def priceAPI(index: int, instrument: str):
    async with aiohttp.ClientSession() as session:
        async with session.get(f"https://test.deribit.com/api/v2/public/get_last_trades_by_instrument?count=1&instrument_name={instrument}") as response:
            try:
                if response.status == 200:
                    data = await response.json()
                    if "result" in data.keys():
                        if (data["result"].get("has_more") == True):
                            data = eval(str(data["result"].get("trades")[0]))
                            market_prices[index] = data.get("index_price")*data.get("mark_price")
                            BitcoinMarketPrice[index] = data.get("index_price")
                            iv[index] = data.get("iv")/100
                            SaleTimes[index] = datetime.fromtimestamp(data.get("timestamp")/1000).astimezone()
                    await GabagoolCollect()
                elif response.status == 429:
                    await asyncio.sleep(1)
                    await priceAPI(index, instrument)
                else:
                    st.write(f"An API request failed with status code: {response.status} - {response.reason}")
            except Exception as e:
                pass


async def GabagoolCollect():
    global GabagoolCollections
    global StartTimeSfCalls
    if GabagoolCollections < InstrumentsToPlay:
        GabagoolCollections += 1
    status = GabagoolCollections/(InstrumentsToPlay)
    my_bar.progress(status, text=f"Collecting data... (Estimated Time to Complete: {math.ceil(((time.time()-StartTimeSfCalls)/status)*(1.0-status))} Seconds)")

async def GetRiskFreeRate():
    year = datetime.now().year
    df = pd.read_csv(f"https://home.treasury.gov/resource-center/data-chart-center/interest-rates/daily-treasury-rates.csv/{year}/all?type=daily_treasury_yield_curve&field_tdr_date_value={year}&page&_format=csv")
    global RiskFreeRateByDaysTillMaturity
    RiskFreeRateByDaysTillMaturity[28] = df.iloc[0]["1 Mo"]/100
    RiskFreeRateByDaysTillMaturity[42] = df.iloc[0]["1.5 Month"]/100
    RiskFreeRateByDaysTillMaturity[56] = df.iloc[0]["2 Mo"]/100
    RiskFreeRateByDaysTillMaturity[91] = df.iloc[0]["3 Mo"]/100
    RiskFreeRateByDaysTillMaturity[119] = df.iloc[0]["4 Mo"]/100
    RiskFreeRateByDaysTillMaturity[182] = df.iloc[0]["6 Mo"]/100
    RiskFreeRateByDaysTillMaturity[364] = df.iloc[0]["1 Yr"]/100
    await GabagoolCollect()

def BlackSholesCall(S: float, K: float, T: float, r: float, sigma: float) -> float:
    d1 = (math.log(S / K) + (r + (sigma ** 2) / 2) * T) / (sigma * math.sqrt(T))
    d2 = d1 - sigma * math.sqrt(T)
    return S * stats.norm.cdf(d1) - K * math.exp(-r * T) * stats.norm.cdf(d2)

def BlackSholesPut(S, K, T, r, sigma):
    d1 = (math.log(S / K) + (r + (sigma ** 2) / 2) * T) / (sigma * math.sqrt(T))
    d2 = d1 - sigma * math.sqrt(T)
    return K * math.exp(-r * T) * stats.norm.cdf(-d2) - S * stats.norm.cdf(-d1)

def BachelierCall(S, K, T, sigma):
    d = (K-S) / (sigma * math.sqrt(T))
    return ((K-S) * stats.norm.cdf(d) - sigma * math.sqrt(T) * stats.norm.pdf(d))

def BachelierPut(S, K, T, sigma):
    d = (K-S) / (sigma * math.sqrt(T))
    return ((S-K) * stats.norm.cdf(-d) - sigma * math.sqrt(T) * stats.norm.pdf(d))

async def main():
    calls = None
    puts = None
    df = None
    if st.button("Update Data"):
        progress_text = "Initializing data collection..."
        global my_bar
        my_bar = st.progress(0, text=progress_text)
        OptionsList = requests.get(url = "https://test.deribit.com/api/v2/public/get_instruments?currency=BTC&expired=false&kind=option")
        OptionsList = json.loads(OptionsList.text)["result"]
        instruments = []
        strikes = []
        options = []
        expiration_dates = []
        a = 0
        tasks = []

        for i in OptionsList:
            if i.get("counter_currency") == "USD":
                instruments.append(i.get("instrument_name"))
                tasks.append(priceAPI(a, i.get("instrument_name")))
                strikes.append(i.get("strike"))
                options.append(i.get("option_type"))
                expire = (datetime.fromtimestamp(i.get("expiration_timestamp")/1000) - datetime.now())
                expiration_dates.append(float(expire.days) + float(expire.seconds/86400))
                a+=1  
        global GabagoolCollections
        GabagoolCollections = 0
        global InstrumentsToPlay
        InstrumentsToPlay = a+2

        init = 0.0
        global market_prices
        market_prices = [init] * len(instruments)
        global iv
        iv = [init] * len(instruments)
        global BitcoinMarketPrice
        BitcoinMarketPrice = [init] * len(instruments)

        global SaleTimes
        SaleTimes = [datetime.now()] * len(instruments)

        global StartTimeSfCalls

        tasks.append(GetRiskFreeRate())
        my_bar.progress(0, text="Starting API Calls...")
        StartTimeSfCalls = time.time()
        await asyncio.gather(*tasks)
        
        df = pd.DataFrame({
            "Instrument": instruments,
            "Strike": strikes,
            "Market Price": market_prices,
            "Implied Volatility": iv,
            "Option Type": options,
            "Expiration": expiration_dates,
            "Sale Time": SaleTimes,
            "Spot": BitcoinMarketPrice
        })



        df = df.dropna()
        df = df[df["Market Price"] != 0]
        df["Strike/Spot"] = df["Strike"]/df["Spot"]
        df.index = range(0, len(df))
        my_bar.progress(1.0, text="Done Collecting Data!")
        my_bar2 = st.progress(0, text="Analyzing data...")
        keys = sorted(RiskFreeRateByDaysTillMaturity.keys())
        
        for i in range(len(df["Instrument"])):
            Strike = df.iloc[i]["Strike"]
            Price = df.iloc[i]["Market Price"]
            Spot = df.iloc[i]["Spot"]
            TimeToExpiration = df.iloc[i]["Expiration"]
            RiskFreeRate = RiskFreeRateByDaysTillMaturity[keys[0]]
            for key in keys:
                if df.iloc[i]["Expiration"] > key:
                    break
                RiskFreeRate = RiskFreeRateByDaysTillMaturity[key]
                
            ForwardPrice = Spot * math.exp(RiskFreeRate * TimeToExpiration/365)

            if df.iloc[i]["Option Type"] == "call":
                df.at[i, "Moneyness"] = 1 - df.at[i, "Strike/Spot"]
                df.at[i, "Evenness"] = Strike+Price
                try:
                    df.at[i, "Black Sholes IV"] = ql.blackFormulaImpliedStdDev(ql.Option.Call, Strike, ForwardPrice, Price, math.exp(-RiskFreeRate * TimeToExpiration/365) )
                    df.at[i, "Black Sholes IV (Time Independent)"] = df.at[i, "Black Sholes IV"]/math.sqrt(TimeToExpiration/365)

                    BlackSholesData = ql.BlackCalculator(ql.PlainVanillaPayoff(ql.Option.Call, Strike), ForwardPrice, df.at[i, "Black Sholes IV"])
                    df.at[i, "Black Sholes Vega"] = BlackSholesData.vega(TimeToExpiration)
                    df.at[i, "Black Sholes Theta"] = BlackSholesData.theta(Spot,TimeToExpiration)
                    df.at[i, "Black Sholes Rho"] = BlackSholesData.rho(TimeToExpiration)
                    df.at[i, "Black Sholes Delta"] = BlackSholesData.delta(Spot)
                    df.at[i, "Black Sholes Gamma"] = BlackSholesData.gamma(Spot)
                    df.at[i, "Black Sholes Alpha"] = BlackSholesData.alpha()
                    df.at[i, "Black Sholes Beta"] = BlackSholesData.beta()
                except Exception as e:
                    pass
                try:
                    df.at[i, "Bachelier IV"] = ql.bachelierBlackFormulaImpliedVol(ql.Option.Call, Strike, ForwardPrice, Price, math.exp(-RiskFreeRate * TimeToExpiration/365) )
                    df.at[i, "Bachelier IV (Time Independent)"] = df.at[i, "Bachelier IV"] / math.sqrt(TimeToExpiration/365)

                    BachelierData = ql.BachelierCalculator(ql.PlainVanillaPayoff(ql.Option.Call, Strike), ForwardPrice, df.at[i, "Bachelier IV"])
                    df.at[i, "Bachelier Vega"] = BachelierData.vega(TimeToExpiration)
                    df.at[i, "Bachelier Theta"] = BachelierData.theta(Spot,TimeToExpiration)
                    df.at[i, "Bachelier Rho"] = BachelierData.rho(TimeToExpiration)
                    df.at[i, "Bachelier Delta"] = BachelierData.delta(Spot)
                    df.at[i, "Bachelier Gamma"] = BachelierData.gamma(Spot)
                    df.at[i, "Bachelier Alpha"] = BachelierData.alpha()
                    df.at[i, "Bachelier Beta"] = BachelierData.beta()

                except Exception as e:
                    pass

                #df.at[i, "Bachelier IV"] = ql.BachelierCalculator(ql.PlainVanillaPayoff(ql.Option.Call, K), S, T, r, sigma).value()
                #df.at[i, "Bachelier IV (Time Independent)"] = ql.BachelierCalculator(ql.PlainVanillaPayoff(ql.Option.Call, K), S, T, r, sigma).value()

            if df.iloc[i]["Option Type"] == "put":
                df.at[i, "Moneyness"] =  df.at[i, "Strike/Spot"] - 1
                try:
                    df.at[i, "Black Sholes IV"] = ql.blackFormulaImpliedStdDev(ql.Option.Put, Strike, ForwardPrice, Price, math.exp(-RiskFreeRate * TimeToExpiration/365) )
                    df.at[i, "Black Sholes IV (Time Independent)"] = df.at[i, "Black Sholes IV"]/math.sqrt(TimeToExpiration/365)

                    BlackSholesData = ql.BlackCalculator(ql.PlainVanillaPayoff(ql.Option.Put, Strike), ForwardPrice, df.at[i, "Black Sholes IV"])
                    df.at[i, "Black Sholes Vega"] = BlackSholesData.vega(TimeToExpiration)
                    df.at[i, "Black Sholes Theta"] = BlackSholesData.theta(Spot, TimeToExpiration)
                    df.at[i, "Black Sholes Rho"] = BlackSholesData.rho(TimeToExpiration)
                    df.at[i, "Black Sholes Delta"] = BlackSholesData.delta(Spot)
                    df.at[i, "Black Sholes Gamma"] = BlackSholesData.gamma(Spot)
                    df.at[i, "Black Sholes Alpha"] = BlackSholesData.alpha()
                    df.at[i, "Black Sholes Beta"] = BlackSholesData.beta()
                except Exception as e:
                    pass
                try:
                    df.at[i, "Bachelier IV"] = ql.bachelierBlackFormulaImpliedVol(ql.Option.Put, Strike, ForwardPrice, Price, math.exp(-RiskFreeRate * TimeToExpiration/365) )
                    df.at[i, "Bachelier IV (Time Independent)"] = df.at[i, "Bachelier IV"] / math.sqrt(TimeToExpiration/365)

                    BachelierData = ql.BachelierCalculator(ql.PlainVanillaPayoff(ql.Option.Call, Strike), ForwardPrice, df.at[i, "Bachelier IV"])
                    df.at[i, "Bachelier Vega"] = BachelierData.vega(TimeToExpiration)
                    df.at[i, "Bachelier Theta"] = BachelierData.theta(Spot,TimeToExpiration)
                    df.at[i, "Bachelier Rho"] = BachelierData.rho(TimeToExpiration)
                    df.at[i, "Bachelier Delta"] = BachelierData.delta(Spot)
                    df.at[i, "Bachelier Gamma"] = BachelierData.gamma(Spot)
                    df.at[i, "Bachelier Alpha"] = BachelierData.alpha()
                    df.at[i, "Bachelier Beta"] = BachelierData.beta()

                except Exception as e:
                    pass
            my_bar2.progress(float(i)/float(len(df["Instrument"])), text="Analyzing data...")
                

        df["Outlier"] = [None] * len(df)
        calls = df[df["Option Type"] == "call"]
        calls.index = range(len(calls))
        puts = df[df["Option Type"] == "put"]
        puts.index = range(len(puts))


        my_bar2.progress(1.0, text="Done Analyzing data!")

        st.session_state["TableData"] = {
            "Calls": calls,
            "Puts": puts,
            "Both": df
        }

    if "TableData" in st.session_state:
        option = st.selectbox(
            "Options Data:",
            ("Both", "Calls", "Puts"),
        )
        data = st.session_state["TableData"][option]
        datatable = st.empty()
        datatable.dataframe(data)

        col = data.columns.tolist()
        col.remove("Instrument")
        col.remove("Option Type")
        col.remove("Sale Time")


        LookToDetect = st.multiselect(
                    "Select Variables For Outlier Detection",
                    col
        )
        neighbors = st.number_input(label = "Number of Neighbors to Look at", min_value=1, step=1)
        if len(LookToDetect) != 0:
            X = data[LookToDetect].dropna()
            clf = LocalOutlierFactor(n_neighbors=int(neighbors))
            data.loc[X.index, "Outlier"] = clf.fit_predict(X.values.tolist())
        else:
            df["Outlier"] = [None] * len(df)



        clients = st.multiselect(
            "Select Variables For 3D Plot",
            col,
            max_selections=3
        )

        if len(clients) == 3:
            clients.append("Outlier")
            temp = data[clients].dropna()
            
            colors = {-1: "Outlier", 1: "Regular"}
            temp["Outlier"] = temp["Outlier"].map(colors)
            fig = px.scatter_3d(
            temp,
            x=clients[0],
            y=clients[1],
            z=clients[2],
            color = clients[3]
            )
            fig.update_traces(marker=dict(size=4))
            fig.update_layout(
            height=650,
            margin=dict(l=0, r=0, t=30, b=0),
            scene=dict(
                xaxis_title=clients[0],
                yaxis_title=clients[1],
                zaxis_title=clients[2],
            ),
            )

            st.plotly_chart(fig, use_container_width=True)
            

            x = temp.iloc[:, 0].to_numpy()
            y = temp.iloc[:, 1].to_numpy()
            z = temp.iloc[:, 2].to_numpy()

            xi = np.linspace(x.min(), x.max(), 100)
            yi = np.linspace(y.min(), y.max(), 100)
            X, Y = np.meshgrid(xi, yi)

            # Interpolate
            Z = griddata(
                (x, y),
                z,
                (X, Y),
                method="linear"
            )

            # Create surface
            fig2 = graph.Figure(data=[graph.Surface(
                x=X,
                y=Y,
                z=Z,
                colorscale="Viridis",
                connectgaps=False,
                contours=dict(
                    z=dict(show=True, usecolormap=True, project_z=True)
                )
            )])

            fig2.update_layout(
                scene=dict(
                    xaxis_title=temp.columns[0],
                    yaxis_title=temp.columns[1],
                    zaxis_title=temp.columns[2],
                    camera=dict(eye=dict(x=1.6, y=-1.4, z=0.8))
                ),
                height=700
            )

            st.plotly_chart(fig2, use_container_width=True)

        clients2 = st.multiselect(
            "Select Variables For 2D Plot",
            col,
            max_selections=2
        )

        if len(clients2) == 2:
            temp = data[clients2]
            st.scatter_chart(
            temp,
            x=clients2[0],
            y=clients2[1],
            color=["#C1631F"],
            )

        DistinctExperationTimes = data["Expiration"].unique()
        option2 = st.selectbox(
                    "Volitility By Strike & Days Till Expiration:",
                    DistinctExperationTimes,
                )
        temp = data[data["Expiration"] == option2]
        st.scatter_chart(
                    temp,
                    x="Strike",
                    y="Black Sholes IV (Time Independent)",
                    color=["#C1631F"],
        )
        







asyncio.run(main())

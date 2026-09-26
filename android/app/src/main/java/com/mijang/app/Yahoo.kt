package com.mijang.app

import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL

object Net {
    fun get(url: String): String {
        val conn = URL(url).openConnection() as HttpURLConnection
        conn.setRequestProperty("User-Agent", "Mozilla/5.0")
        conn.connectTimeout = 15_000
        conn.readTimeout = 15_000
        try {
            return conn.inputStream.bufferedReader().use { it.readText() }
        } finally {
            conn.disconnect()
        }
    }
}

/** GitHub Actions가 매일 학습해 main에 올리는 예측 결과. */
object Predictions {
    private const val URL = "https://raw.githubusercontent.com/akskekekdk/mijang/main/data/predictions.json"

    /** 예측 요약과, 근거 화면용 원본 JSON. */
    fun fetch(): Pair<Prediction, String> {
        val json = Net.get(URL)
        return Prediction.parse(json) to json
    }
}

/** Yahoo Finance 차트 API (키 불필요). */
object Yahoo {
    /** 현재가와 전일 종가. */
    fun quote(ticker: String): Pair<Double, Double> {
        val body = Net.get("https://query1.finance.yahoo.com/v8/finance/chart/$ticker?range=1d&interval=1d")
        val meta = JSONObject(body).getJSONObject("chart").getJSONArray("result")
            .getJSONObject(0).getJSONObject("meta")
        return meta.getDouble("regularMarketPrice") to meta.getDouble("chartPreviousClose")
    }
}

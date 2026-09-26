package com.mijang.app

import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL

/** Yahoo Finance 차트 API (키 불필요). */
object Yahoo {
    private const val BASE = "https://query1.finance.yahoo.com/v8/finance/chart/"

    private fun chart(ticker: String, range: String, interval: String): JSONObject {
        val conn = URL("$BASE$ticker?range=$range&interval=$interval").openConnection() as HttpURLConnection
        conn.setRequestProperty("User-Agent", "Mozilla/5.0")
        conn.connectTimeout = 15_000
        conn.readTimeout = 15_000
        try {
            val body = conn.inputStream.bufferedReader().use { it.readText() }
            return JSONObject(body).getJSONObject("chart").getJSONArray("result").getJSONObject(0)
        } finally {
            conn.disconnect()
        }
    }

    /** 최근 5년 주간 수정종가 (배당 재투자 반영). */
    fun weekly5y(ticker: String): Series {
        val r = chart(ticker, "5y", "1wk")
        val ts = r.getJSONArray("timestamp")
        val adj = r.getJSONObject("indicators").getJSONArray("adjclose")
            .getJSONObject(0).getJSONArray("adjclose")
        val n = minOf(ts.length(), adj.length())
        return Series(
            times = (0 until n).map { ts.getLong(it) },
            closes = (0 until n).map { adj.optDouble(it) },
        )
    }

    /** 현재가와 전일 종가. */
    fun quote(ticker: String): Pair<Double, Double> {
        val meta = chart(ticker, "1d", "1d").getJSONObject("meta")
        return meta.getDouble("regularMarketPrice") to meta.getDouble("chartPreviousClose")
    }
}

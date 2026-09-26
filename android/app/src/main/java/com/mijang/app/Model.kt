package com.mijang.app

import org.json.JSONArray
import org.json.JSONObject

/** 5년 수익률 순위에 든 종목과 현재 시세. */
data class Stock(
    val ticker: String,
    val name: String,
    val return5y: Double,
    val cagr: Double,
    val price: Double = Double.NaN,
    val prevClose: Double = Double.NaN,
) {
    val change: Double get() = price / prevClose - 1

    fun toJson(): JSONObject = JSONObject()
        .put("ticker", ticker).put("name", name)
        .put("return5y", return5y).put("cagr", cagr)
        .put("price", price.orNull()).put("prevClose", prevClose.orNull())

    companion object {
        fun fromJson(o: JSONObject) = Stock(
            ticker = o.getString("ticker"),
            name = o.getString("name"),
            return5y = o.getDouble("return5y"),
            cagr = o.getDouble("cagr"),
            price = o.optDouble("price"),
            prevClose = o.optDouble("prevClose"),
        )
    }
}

/** 마지막 갱신 결과. rankedAt 은 순위 계산 시각, quotedAt 은 시세 조회 시각 (epoch ms). */
data class Snapshot(val stocks: List<Stock>, val rankedAt: Long, val quotedAt: Long) {
    fun toJson(): String = JSONObject()
        .put("rankedAt", rankedAt)
        .put("quotedAt", quotedAt)
        .put("stocks", JSONArray(stocks.map { it.toJson() }))
        .toString()

    companion object {
        fun fromJson(s: String): Snapshot {
            val o = JSONObject(s)
            val arr = o.getJSONArray("stocks")
            return Snapshot(
                stocks = (0 until arr.length()).map { Stock.fromJson(arr.getJSONObject(it)) },
                rankedAt = o.getLong("rankedAt"),
                quotedAt = o.getLong("quotedAt"),
            )
        }
    }
}

private fun Double.orNull(): Any = if (isNaN()) JSONObject.NULL else this

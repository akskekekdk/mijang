package com.mijang.app

import org.json.JSONArray
import org.json.JSONObject

/** 모델이 고른 종목과 현재 시세. prob = 향후 3개월 SPY를 이길 확률(모델 추정). */
data class Stock(
    val ticker: String,
    val name: String,
    val prob: Double,
    val price: Double = Double.NaN,
    val prevClose: Double = Double.NaN,
) {
    val change: Double get() = price / prevClose - 1

    fun toJson(): JSONObject = JSONObject()
        .put("ticker", ticker).put("name", name).put("prob", prob)
        .put("price", price.orNull()).put("prevClose", prevClose.orNull())

    companion object {
        fun fromJson(o: JSONObject) = Stock(
            ticker = o.getString("ticker"),
            name = o.getString("name"),
            prob = o.getDouble("prob"),
            price = o.optDouble("price"),
            prevClose = o.optDouble("prevClose"),
        )
    }
}

/** 예측 파일(data/predictions.json)에서 앱이 쓰는 부분. */
data class Prediction(val asOf: String, val stocks: List<Stock>, val backtest: String) {
    companion object {
        fun parse(json: String): Prediction {
            val o = JSONObject(json)
            val arr = o.getJSONArray("stocks")
            val bt = o.getJSONObject("backtest")
            val summary = "백테스트 ${bt.getString("period")}: 상위20 3개월 초과수익 " +
                "${Format.percent(bt.getDouble("top_avg_excess_3m"))} " +
                "(전체 ${Format.percent(bt.getDouble("universe_avg_excess_3m"))}), " +
                "AUC ${String.format(java.util.Locale.US, "%.2f", bt.getDouble("auc"))}"
            return Prediction(
                asOf = o.getString("as_of"),
                stocks = (0 until arr.length()).map { Stock.fromJson(arr.getJSONObject(it)) },
                backtest = summary,
            )
        }
    }
}

/** 마지막 갱신 결과. fetchedAt 은 예측 파일 받은 시각, quotedAt 은 시세 조회 시각 (epoch ms). */
data class Snapshot(
    val prediction: Prediction,
    val fetchedAt: Long,
    val quotedAt: Long,
) {
    val stocks: List<Stock> get() = prediction.stocks

    fun toJson(): String = JSONObject()
        .put("asOf", prediction.asOf)
        .put("backtest", prediction.backtest)
        .put("fetchedAt", fetchedAt)
        .put("quotedAt", quotedAt)
        .put("stocks", JSONArray(stocks.map { it.toJson() }))
        .toString()

    companion object {
        fun fromJson(s: String): Snapshot {
            val o = JSONObject(s)
            val arr = o.getJSONArray("stocks")
            return Snapshot(
                prediction = Prediction(
                    asOf = o.getString("asOf"),
                    stocks = (0 until arr.length()).map { Stock.fromJson(arr.getJSONObject(it)) },
                    backtest = o.getString("backtest"),
                ),
                fetchedAt = o.getLong("fetchedAt"),
                quotedAt = o.getLong("quotedAt"),
            )
        }
    }
}

private fun Double.orNull(): Any = if (isNaN()) JSONObject.NULL else this

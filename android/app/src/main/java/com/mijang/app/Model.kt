package com.mijang.app

import org.json.JSONArray
import org.json.JSONObject
import java.util.Locale

/** 시세. */
data class Quote(val price: Double, val prevClose: Double) {
    val change: Double get() = price / prevClose - 1

    fun toJson(): JSONObject = JSONObject().put("price", price).put("prevClose", prevClose)

    companion object {
        fun fromJson(o: JSONObject) = Quote(o.getDouble("price"), o.getDouble("prevClose"))
    }
}

/** 매수추천 종목. score = 오늘 후보 중 순위(0~1, 1이 최고). */
data class Stock(
    val ticker: String,
    val name: String,
    val score: Double,
    val price: Double = Double.NaN,
    val prevClose: Double = Double.NaN,
) {
    val change: Double get() = price / prevClose - 1

    fun withQuote(q: Quote?) = if (q == null) this else copy(price = q.price, prevClose = q.prevClose)

    fun toJson(): JSONObject = JSONObject()
        .put("ticker", ticker).put("name", name).put("score", score)
        .put("price", price.orNull()).put("prevClose", prevClose.orNull())

    companion object {
        fun fromJson(o: JSONObject) = Stock(
            ticker = o.getString("ticker"),
            name = o.getString("name"),
            score = o.getDouble("score"),
            price = o.optDouble("price"),
            prevClose = o.optDouble("prevClose"),
        )
    }
}

/** 예측 파일(data/predictions.json)에서 앱이 쓰는 부분. */
data class Prediction(val asOf: String, val stocks: List<Stock>, val method: String, val summary: String) {
    companion object {
        fun parse(json: String): Prediction {
            val o = JSONObject(json)
            val arr = o.getJSONArray("stocks")
            val acc = o.getJSONObject("accuracy")
            val hold = o.getJSONObject("holdout")
            val methods = o.getJSONArray("methods").length()
            val label = o.getJSONObject("method").getString("label")
            val summary = "예측 방법: $label (${methods}가지 방법 중 과거 적중률 1위)\n" +
                "과거 적중률 ${pct(acc.getDouble("hit_rate"))} (무작위 ${pct(acc.getDouble("universe_hit_rate"))}) · " +
                "최근 검증 ${pct(hold.getDouble("hit_rate"))}\n" +
                "추천 종목 3개월 평균 SPY 대비 ${Format.percent(acc.getDouble("avg_excess_3m"))} " +
                "(전체 ${Format.percent(acc.getDouble("universe_avg_excess_3m"))})"
            return Prediction(
                asOf = o.getString("as_of"),
                stocks = (0 until arr.length()).map { Stock.fromJson(arr.getJSONObject(it)) },
                method = label,
                summary = summary,
            )
        }

        private fun pct(v: Double) = String.format(Locale.US, "%.0f%%", v * 100)
    }
}

/** 마지막 갱신 결과. fetchedAt 은 예측 파일 받은 시각, quotedAt 은 시세 조회 시각 (epoch ms). */
data class Snapshot(
    val prediction: Prediction,
    val fetchedAt: Long,
    val quotedAt: Long,
    val quotes: Map<String, Quote> = emptyMap(), // 담은 종목 시세
) {
    val stocks: List<Stock> get() = prediction.stocks

    fun toJson(): String = JSONObject()
        .put("asOf", prediction.asOf)
        .put("method", prediction.method)
        .put("summary", prediction.summary)
        .put("fetchedAt", fetchedAt)
        .put("quotedAt", quotedAt)
        .put("stocks", JSONArray(stocks.map { it.toJson() }))
        .put("quotes", JSONObject().apply { quotes.forEach { (t, q) -> put(t, q.toJson()) } })
        .toString()

    companion object {
        fun fromJson(s: String): Snapshot {
            val o = JSONObject(s)
            val arr = o.getJSONArray("stocks")
            val q = o.optJSONObject("quotes") ?: JSONObject()
            return Snapshot(
                prediction = Prediction(
                    asOf = o.getString("asOf"),
                    stocks = (0 until arr.length()).map { Stock.fromJson(arr.getJSONObject(it)) },
                    method = o.getString("method"),
                    summary = o.getString("summary"),
                ),
                fetchedAt = o.getLong("fetchedAt"),
                quotedAt = o.getLong("quotedAt"),
                quotes = q.keys().asSequence().associateWith { Quote.fromJson(q.getJSONObject(it)) },
            )
        }
    }
}

/** 내가 담은 종목. 추천에서 빠져도 직접 삭제하기 전까지 남는다. */
data class Watched(val ticker: String, val name: String, val addedAt: Long, val addedPrice: Double) {
    fun toJson(): JSONObject = JSONObject()
        .put("ticker", ticker).put("name", name).put("addedAt", addedAt).put("addedPrice", addedPrice.orNull())

    companion object {
        fun fromJson(o: JSONObject) = Watched(
            o.getString("ticker"), o.getString("name"), o.getLong("addedAt"), o.optDouble("addedPrice"),
        )

        fun listToJson(list: List<Watched>): String = JSONArray(list.map { it.toJson() }).toString()

        fun listFromJson(s: String): List<Watched> {
            val arr = JSONArray(s)
            return (0 until arr.length()).map { fromJson(arr.getJSONObject(it)) }
        }
    }
}

private fun Double.orNull(): Any = if (isNaN()) JSONObject.NULL else this

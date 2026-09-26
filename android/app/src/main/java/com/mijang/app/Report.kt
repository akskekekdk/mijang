package com.mijang.app

import org.json.JSONObject

/** 예측 파일의 근거 부분: 방법 비교표, 지표별 과거 성적표, 종목별 상세 근거. */
data class FeatureStat(
    val key: String, val label: String, val description: String, val isPercent: Boolean,
    val topHit: Double, val topExcess: Double, val bottomHit: Double, val bottomExcess: Double,
    val ic: Double, val better: String,
)

data class MethodStat(
    val label: String, val kind: String, val description: String,
    val selectionHit: Double, val selectionExcess: Double, val selectionPeriod: String,
    val holdoutHit: Double, val holdoutExcess: Double, val holdoutPeriod: String,
    val chosen: Boolean,
)

data class Example(val date: String, val name: String, val excess: Double)

data class Similar(val n: Int, val hitRate: Double, val avgExcess: Double, val medianExcess: Double, val examples: List<Example>)

data class Detail(
    val ticker: String, val name: String, val rank: Int, val score: Double, val recommended: Boolean,
    val values: Map<String, Double>, val ranks: Map<String, Double>, val contrib: Map<String, Double>,
    val reasons: List<String>, val similar: Similar,
)

data class Report(
    val asOf: String,
    val candidates: Int,
    val methodLabel: String,
    val baseHitRate: Double,
    val methods: List<MethodStat>,
    val features: List<FeatureStat>,
    val details: Map<String, Detail>,
) {
    companion object {
        fun parse(json: String): Report {
            val o = JSONObject(json)
            val methods = o.getJSONArray("methods").objects().map { m ->
                val s = m.getJSONObject("selection")
                val h = m.getJSONObject("holdout")
                MethodStat(
                    m.getString("label"), m.getString("kind"), m.getString("description"),
                    s.getDouble("hit_rate"), s.getDouble("avg_excess_3m"), s.getString("period"),
                    h.getDouble("hit_rate"), h.getDouble("avg_excess_3m"), h.getString("period"),
                    m.getBoolean("chosen"),
                )
            }
            val features = o.getJSONArray("features").objects().map { f ->
                FeatureStat(
                    f.getString("key"), f.getString("label"), f.getString("description"), f.getString("format") == "pct",
                    f.getDouble("top_hit_rate"), f.getDouble("top_avg_excess"),
                    f.getDouble("bottom_hit_rate"), f.getDouble("bottom_avg_excess"),
                    f.getDouble("ic"), f.getString("better"),
                )
            }
            val d = o.getJSONObject("details")
            val details = d.keys().asSequence().associateWith { t -> parseDetail(t, d.getJSONObject(t)) }
            return Report(
                asOf = o.getString("as_of"),
                candidates = o.getInt("candidates"),
                methodLabel = o.getJSONObject("method").getString("label"),
                baseHitRate = o.getJSONObject("accuracy").getDouble("universe_hit_rate"),
                methods = methods,
                features = features,
                details = details,
            )
        }

        private fun parseDetail(ticker: String, o: JSONObject): Detail {
            val sim = o.getJSONObject("similar")
            return Detail(
                ticker = ticker,
                name = o.getString("name"),
                rank = o.getInt("rank"),
                score = o.getDouble("score"),
                recommended = o.getBoolean("recommended"),
                values = o.getJSONObject("values").doubles(),
                ranks = o.getJSONObject("ranks").doubles(),
                contrib = o.getJSONObject("contrib").doubles(),
                reasons = o.getJSONArray("reasons").let { a -> (0 until a.length()).map { a.getString(it) } },
                similar = Similar(
                    sim.getInt("n"), sim.getDouble("hit_rate"), sim.getDouble("avg_excess"), sim.getDouble("median_excess"),
                    sim.getJSONArray("examples").objects().map {
                        Example(it.getString("date"), it.getString("name"), it.getDouble("excess"))
                    },
                ),
            )
        }

        private fun org.json.JSONArray.objects(): List<JSONObject> = (0 until length()).map { getJSONObject(it) }

        /** null 값은 빼고 담는다. */
        private fun JSONObject.doubles(): Map<String, Double> =
            keys().asSequence().filter { !isNull(it) }.associateWith { getDouble(it) }
    }
}

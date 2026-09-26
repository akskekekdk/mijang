package com.mijang.app

import kotlin.math.pow

/** 주간 수정종가 시계열 (epoch 초, 종가). */
data class Series(val times: List<Long>, val closes: List<Double>)

object Ranker {
    private const val YEAR_SECONDS = 365.25 * 24 * 3600
    private const val GRACE_SECONDS = 31L * 24 * 3600

    /**
     * 5년 치 데이터가 온전히 있는 종목만 누적 수익률 순으로 [top]개 고른다.
     * [now] 는 epoch 초.
     */
    fun rank(
        series: Map<String, Series>,
        names: Map<String, String>,
        now: Long,
        top: Int = 20,
        years: Int = 5,
    ): List<Stock> {
        val startLimit = now - (years * YEAR_SECONDS).toLong() + GRACE_SECONDS
        return series.mapNotNull { (ticker, s) ->
            val points = s.times.zip(s.closes).filter { !it.second.isNaN() }
            if (points.size < 2) return@mapNotNull null
            val (t0, p0) = points.first()
            val (t1, p1) = points.last()
            if (t0 > startLimit || p0 <= 0) return@mapNotNull null // 상장 5년 미만
            val total = p1 / p0 - 1
            val yrs = (t1 - t0) / YEAR_SECONDS
            Stock(ticker, names[ticker] ?: ticker, total, (p1 / p0).pow(1 / yrs) - 1)
        }.sortedByDescending { it.return5y }.take(top)
    }
}

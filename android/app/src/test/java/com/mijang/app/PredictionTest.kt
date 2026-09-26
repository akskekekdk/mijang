package com.mijang.app

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.File

class PredictionTest {
    /** 저장소의 실제 예측 파일을 앱 파서가 읽을 수 있는지 (Python 출력 형식과 앱이 어긋나지 않도록). */
    @Test
    fun parsesRepoPredictionsFile() {
        val p = Prediction.parse(File("../../data/predictions.json").readText())
        assertEquals(20, p.stocks.size)
        assertTrue(p.stocks.all { it.score in 0.0..1.0 && it.name.isNotEmpty() })
        assertTrue(p.stocks.zipWithNext().all { (a, b) -> a.score >= b.score })
        assertTrue(p.summary.startsWith("예측 방법: ${p.method}"))
    }

    @Test
    fun snapshotRoundTrip() {
        val p = Prediction("2026-09-25", listOf(Stock("NVDA", "엔비디아", 0.97, 225.07, 224.58)), "앙상블", "요약")
        val snap = Snapshot(p, 1L, 2L, mapOf("AAPL" to Quote(250.0, 245.0)))
        val back = Snapshot.fromJson(snap.toJson())
        assertEquals(snap, back)
        assertEquals(250.0 / 245.0 - 1, back.quotes.getValue("AAPL").change, 1e-12)
    }

    @Test
    fun watchlistRoundTrip() {
        val list = listOf(Watched("NVDA", "엔비디아", 123L, 225.07), Watched("AAPL", "애플", 456L, Double.NaN))
        val back = Watched.listFromJson(Watched.listToJson(list))
        assertEquals(list[0], back[0])
        assertEquals("AAPL", back[1].ticker)
        assertTrue(back[1].addedPrice.isNaN())
    }
}

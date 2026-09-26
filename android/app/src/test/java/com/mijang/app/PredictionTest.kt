package com.mijang.app

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.File

class PredictionTest {
    /** 저장소의 실제 예측 파일을 앱 파서가 읽을 수 있는지 (Python 출력 형식과 앱이 어긋나지 않도록). */
    @Test
    fun parsesRepoPredictionsFile() {
        val file = File("../../data/predictions.json")
        val p = Prediction.parse(file.readText())
        assertEquals(20, p.stocks.size)
        assertTrue(p.stocks.all { it.prob in 0.0..1.0 && it.name.isNotEmpty() })
        assertTrue(p.stocks.zipWithNext().all { (a, b) -> a.prob >= b.prob })
        assertTrue(p.backtest.startsWith("백테스트"))
    }

    @Test
    fun snapshotRoundTrip() {
        val p = Prediction("2026-09-25", listOf(Stock("NVDA", "엔비디아", 0.57, 225.07, 224.58)), "백테스트 x")
        val back = Snapshot.fromJson(Snapshot(p, 1L, 2L).toJson())
        assertEquals(p, back.prediction)
        assertEquals(225.07 / 224.58 - 1, back.stocks[0].change, 1e-12)
    }
}

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

class ReportTest {
    /** 근거 화면이 읽는 부분(방법표·지표표·종목 상세)이 Python 출력과 맞는지. */
    @Test
    fun parsesRepoReport() {
        val json = File("../../data/predictions.json").readText()
        val r = Report.parse(json)
        val p = Prediction.parse(json)
        assertEquals(1, r.methods.count { it.chosen })
        assertEquals(p.method, r.methodLabel)
        assertTrue(r.features.map { it.key }.containsAll(listOf("per", "pbr", "roe", "sharpe")))
        assertEquals(r.candidates, r.details.size)
        p.stocks.forEachIndexed { i, s ->
            val d = r.details.getValue(s.ticker)
            assertEquals(i + 1, d.rank)
            assertTrue(d.recommended)
            assertEquals(r.features.size - 1, d.contrib.size) // CAGR은 모델 입력이 아니라 기여도 없음
            assertEquals(3, d.similar.examples.size)
        }
        assertTrue(r.details.values.count { it.recommended } == p.stocks.size)
    }
}

class UpdaterTest {
    /** CI(android.yml)가 만드는 version.json 형식을 앱이 읽을 수 있는지. */
    @Test
    fun parsesCiVersionFile() {
        val r = Updater.parse("""{"versionCode":12,"versionName":"1.0.12","sha":"abc1234"}""")
        assertEquals(12L, r.versionCode)
        assertEquals("1.0.12", r.versionName)
    }
}

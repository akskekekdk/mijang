package com.mijang.app

import android.content.Context
import android.content.Intent
import android.os.Bundle
import android.widget.Button
import android.widget.LinearLayout
import android.widget.TextView
import androidx.activity.ComponentActivity
import java.util.Locale
import kotlin.math.roundToInt

/** 종목 하나의 추천 근거: 이유, 비슷한 과거 사례, 지표 23개 표. */
class DetailActivity : ComponentActivity() {
    private lateinit var ui: Ui
    private lateinit var ticker: String

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_page)
        ticker = intent.getStringExtra(EXTRA_TICKER) ?: return finish()
        ui = Ui(this, findViewById<LinearLayout>(R.id.content))
        render()
    }

    private fun render() {
        ui.clear()
        val report = Store.report(this)
        val detail = report?.details?.get(ticker)
        val snapshot = Store.load(this)
        val watched = Store.watchlist(this).any { it.ticker == ticker }
        val quote = snapshot?.quotes?.get(ticker)
            ?: snapshot?.stocks?.firstOrNull { it.ticker == ticker }?.let { Quote(it.price, it.prevClose) }
        val name = detail?.name ?: Store.watchlist(this).firstOrNull { it.ticker == ticker }?.name ?: ticker

        findViewById<TextView>(R.id.page_title).text = "$name ($ticker)"
        findViewById<Button>(R.id.page_action).apply {
            text = getString(if (watched) R.string.remove else R.string.add)
            setOnClickListener {
                if (watched) Store.removeWatch(this@DetailActivity, ticker)
                else Store.addWatch(this@DetailActivity, ticker, name, quote?.price ?: Double.NaN)
                render()
            }
        }
        if (quote != null) ui.body(Format.quoteLine(this, "현재가", quote.price, quote.change))
        if (report == null || detail == null) {
            ui.note("이 종목의 근거 데이터가 아직 없어요. 메인 화면에서 새로고침을 눌러주세요.")
            return
        }

        ui.note(
            (if (detail.recommended) "매수추천 ${detail.rank}위" else "추천 아님 · 후보 ${report.candidates}개 중 ${detail.rank}위") +
                " · 점수 ${(detail.score * 100).roundToInt()} · ${report.asOf} 종가 기준 · 예측 방법: ${report.methodLabel}"
        )

        ui.title("왜 이 점수인가")
        if (detail.reasons.isEmpty()) ui.body("점수를 크게 움직인 지표가 없어요 (대부분 보통 수준).")
        detail.reasons.forEach { ui.body("• $it") }
        ui.note("%p = 그 지표를 '보통'(후보 중 가운데)으로 바꾸면 이 종목의 순위가 몇 %p 바뀌는지. 아래 표의 '영향'과 같은 값입니다.")

        val sim = detail.similar
        ui.title("과거에 지표가 비슷했던 ${sim.n}건")
        ui.body(
            android.text.SpannableStringBuilder()
                .append("3개월 뒤 SPY를 이긴 비율 ").append(ui.bold(pct0(sim.hitRate)))
                .append(" (전체 평균 ${pct0(report.baseHitRate)})\n평균 ")
                .append(ui.signed(pct1(sim.avgExcess), sim.avgExcess))
                .append(" · 중간값 ").append(ui.signed(pct1(sim.medianExcess), sim.medianExcess))
        )
        ui.table(
            listOf("가장 비슷했던 사례", "3개월 뒤 SPY 대비"),
            sim.examples.map { listOf("${it.date} ${it.name}", ui.signed(pct1(it.excess), it.excess)) },
        )

        ui.title("지표 23개")
        ui.table(
            listOf("지표", "값", "후보 중", "영향"),
            report.features.map { f ->
                val v = detail.values[f.key]
                val r = detail.ranks[f.key]
                val c = detail.contrib[f.key]
                listOf(
                    f.label,
                    if (v == null) "-" else if (f.isPercent) pct1(v) else String.format(Locale.US, "%.2f", v),
                    if (r == null) "-" else if (r >= 0.5) "상위 ${((1 - r) * 100).roundToInt().coerceAtLeast(1)}%" else "하위 ${(r * 100).roundToInt().coerceAtLeast(1)}%",
                    if (c == null) "-" else ui.signed(String.format(Locale.US, "%+.0f%%p", c), c / 100),
                )
            },
        )
        ui.note("'후보 중' = 오늘 후보 ${report.candidates}개 가운데 위치. '영향' 빨강은 점수를 올린 지표, 파랑은 깎은 지표.\n" +
            "연평균 수익률은 1년 구간에선 1년 수익률과 같아서 모델 입력에서 뺐습니다.")
        ui.title("지표 설명")
        report.features.forEach { ui.note("${it.label}: ${it.description}") }
    }

    companion object {
        private const val EXTRA_TICKER = "ticker"

        fun open(context: Context, ticker: String) =
            context.startActivity(Intent(context, DetailActivity::class.java).putExtra(EXTRA_TICKER, ticker))

        fun pct0(v: Double) = String.format(Locale.US, "%.0f%%", v * 100)
        fun pct1(v: Double) = String.format(Locale.US, "%+.1f%%", v * 100)
    }
}

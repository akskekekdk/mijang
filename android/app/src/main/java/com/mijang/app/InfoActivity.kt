package com.mijang.app

import android.content.Context
import android.content.Intent
import android.os.Bundle
import android.view.View
import android.widget.Button
import android.widget.LinearLayout
import android.widget.TextView
import androidx.activity.ComponentActivity
import com.mijang.app.DetailActivity.Companion.pct0
import com.mijang.app.DetailActivity.Companion.pct1
import java.util.Locale

/** 어떻게 예측하나: 방법 15가지 비교표, 지표별 과거 성적표. */
class InfoActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_page)
        findViewById<TextView>(R.id.page_title).text = getString(R.string.info_title)
        findViewById<Button>(R.id.page_action).visibility = View.GONE
        val ui = Ui(this, findViewById<LinearLayout>(R.id.content))
        val report = Store.report(this) ?: run {
            ui.note("근거 데이터가 아직 없어요. 메인 화면에서 새로고침을 눌러주세요.")
            return
        }
        val chosen = report.methods.first { it.chosen }

        ui.title("예측하는 방법")
        ui.body(
            "1. 지난 10년 동안 매월 말, 후보 종목마다 직전 1년 가격·거래량으로 지표 23개를 계산합니다.\n" +
                "2. 그 뒤 3개월 동안 S&P 500(SPY)보다 더 올랐는지를 정답으로 기록합니다.\n" +
                "3. 아래 15가지 방법으로 '과거로만 배우고 다음 해를 맞히기'를 반복해 성적을 매깁니다.\n" +
                "4. 선정 기간 적중률 1위 방법(지금은 ${chosen.label})으로 오늘 매수추천 20개를 고릅니다.\n" +
                "매일 아침 7시 30분에 새 데이터로 다시 합니다."
        )

        ui.title("방법 15가지 비교")
        ui.note("적중률 = 추천 20종목 중 3개월 뒤 SPY를 이긴 비율 (아무거나 고르면 ${pct0(report.baseHitRate)})\n" +
            "선정 ${chosen.selectionPeriod} 성적으로 방법을 고르고, 고를 때 안 쓴 검증 ${chosen.holdoutPeriod} 성적을 따로 봅니다.")
        ui.table(
            listOf("방법", "선정 적중", "검증 적중", "검증 초과"),
            report.methods.map { m ->
                listOf(
                    (if (m.chosen) "▶ " else "") + m.label,
                    pct0(m.selectionHit),
                    pct0(m.holdoutHit),
                    ui.signed(pct1(m.holdoutExcess), m.holdoutExcess),
                )
            },
            bold = { report.methods[it].chosen },
        )
        ui.note("검증 초과 = 추천 종목의 3개월 평균 SPY 대비 수익률.\n" +
            "방법이 많을수록 선정 기간 1위가 운일 가능성도 커지므로, 검증 적중률을 함께 보세요.")
        report.methods.forEach { ui.note("${it.label} (${it.kind}): ${it.description}") }

        ui.title("지표별 과거 성적")
        ui.note("그 지표가 후보 중 상위 20% / 하위 20%였던 종목이 3개월 뒤 SPY를 이긴 비율. 차이가 클수록 쓸모 있는 지표.")
        ui.table(
            listOf("지표", "상위20%", "하위20%", "유리"),
            report.features.map { f ->
                listOf(
                    f.label,
                    ui.signed(pct0(f.topHit), f.topHit - report.baseHitRate),
                    ui.signed(pct0(f.bottomHit), f.bottomHit - report.baseHitRate),
                    f.better,
                )
            },
        )
        ui.note("빨강 = 평균(${pct0(report.baseHitRate)})보다 높음, 파랑 = 낮음.\n" +
            "IC(순위 상관) 높은 순: " + report.features.sortedByDescending { kotlin.math.abs(it.ic) }.take(5)
                .joinToString(", ") { "${it.label} ${String.format(Locale.US, "%+.3f", it.ic)}" })
        ui.note("\n" + getString(R.string.disclaimer) +
            "\n후보가 지금 S&P 100·나스닥 100에 있는 종목이라(생존 편향) 과거 성적이 실제보다 좋게 나올 수 있습니다.")
    }

    companion object {
        fun open(context: Context) = context.startActivity(Intent(context, InfoActivity::class.java))
    }
}

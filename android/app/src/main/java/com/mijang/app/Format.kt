package com.mijang.app

import android.content.Context
import android.text.SpannableStringBuilder
import android.text.Spanned
import android.text.style.ForegroundColorSpan
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

object Format {
    private fun color(context: Context, change: Double): Int = context.getColor(
        when {
            change.isNaN() || Math.round(change * 10000) == 0L -> R.color.flat
            change > 0 -> R.color.up
            else -> R.color.down
        }
    )

    fun percent(v: Double, sign: Boolean = true): String =
        if (v.isNaN()) "-" else String.format(Locale.US, if (sign) "%+,.2f%%" else "%,.1f%%", v * 100)

    fun price(v: Double): String = if (v.isNaN()) "-" else String.format(Locale.US, "$%,.2f", v)

    /** "09.26(토) 09:47 기준" */
    fun asOf(millis: Long): String =
        SimpleDateFormat("MM.dd(E) HH:mm 기준", Locale.KOREAN).format(Date(millis))

    /**
     * 종목마다 "1. 엔비디아  $225.07 +0.22%" 한 줄. [firstRank] 는 첫 줄 순위 번호,
     * [withScore] 이면 추천 점수(0~100)도 붙인다.
     */
    fun rows(context: Context, stocks: List<Stock>, firstRank: Int = 1, withScore: Boolean = false): List<CharSequence> =
        stocks.mapIndexed { i, s ->
            val sb = SpannableStringBuilder("${firstRank + i}. ")
            sb.append(quoteLine(context, s.name, s.price, s.change))
            if (withScore) sub(context, sb, "\n점수 ${Math.round(s.score * 100)}")
            sb
        }

    /** "엔비디아  $225.07 +0.22%" (등락률 색칠). */
    fun quoteLine(context: Context, name: String, price: Double, change: Double): CharSequence {
        val sb = SpannableStringBuilder("$name  ${price(price)} ")
        val start = sb.length
        sb.append(percent(change))
        sb.setSpan(ForegroundColorSpan(color(context, change)), start, sb.length, Spanned.SPAN_EXCLUSIVE_EXCLUSIVE)
        return sb
    }

    /** 담은 종목: 시세 줄 + "담은 뒤 +3.4% · 추천 중" */
    fun watchedLine(context: Context, w: Watched, quote: Quote?, recommended: Boolean): CharSequence {
        val price = quote?.price ?: Double.NaN
        val sb = SpannableStringBuilder(quoteLine(context, w.name, price, quote?.change ?: Double.NaN))
        sb.append("\n")
        val since = price / w.addedPrice - 1
        val start = sb.length
        sb.append("담은 뒤 ${percent(since)}")
        sb.setSpan(ForegroundColorSpan(color(context, since)), start, sb.length, Spanned.SPAN_EXCLUSIVE_EXCLUSIVE)
        sub(context, sb, " · ${SimpleDateFormat("MM.dd", Locale.KOREAN).format(Date(w.addedAt))} 담음 · " +
            if (recommended) "추천 중" else "추천 종료")
        return sb
    }

    private fun sub(context: Context, sb: SpannableStringBuilder, text: String) {
        val start = sb.length
        sb.append(text)
        sb.setSpan(ForegroundColorSpan(context.getColor(R.color.sub)), start, sb.length, Spanned.SPAN_EXCLUSIVE_EXCLUSIVE)
    }
}

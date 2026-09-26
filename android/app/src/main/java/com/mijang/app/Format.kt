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
     * "1. 엔비디아  $225.07 +0.22%" 형태의 줄들. [firstRank] 는 첫 줄 순위 번호,
     * [withReturn] 이면 5년 수익률도 붙인다.
     */
    fun lines(context: Context, stocks: List<Stock>, firstRank: Int = 1, withReturn: Boolean = false): CharSequence {
        val sb = SpannableStringBuilder()
        stocks.forEachIndexed { i, s ->
            if (i > 0) sb.append('\n')
            sb.append("${firstRank + i}. ${s.name}  ${price(s.price)} ")
            val start = sb.length
            sb.append(percent(s.change))
            sb.setSpan(ForegroundColorSpan(color(context, s.change)), start, sb.length, Spanned.SPAN_EXCLUSIVE_EXCLUSIVE)
            if (withReturn) {
                val subStart = sb.length
                sb.append("   5년 ${percent(s.return5y, sign = false)}")
                sb.setSpan(ForegroundColorSpan(context.getColor(R.color.sub)), subStart, sb.length, Spanned.SPAN_EXCLUSIVE_EXCLUSIVE)
            }
        }
        return sb
    }
}

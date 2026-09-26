package com.mijang.app

import android.app.Activity
import android.graphics.Typeface
import android.text.SpannableString
import android.text.Spanned
import android.text.style.ForegroundColorSpan
import android.text.style.StyleSpan
import android.util.TypedValue
import android.view.Gravity
import android.view.LayoutInflater
import android.widget.LinearLayout
import android.widget.TableLayout
import android.widget.TableRow
import android.widget.TextView

/** 화면을 코드로 쌓아 올리는 작은 도우미 (제목 / 설명 / 표). */
class Ui(private val activity: Activity, private val content: LinearLayout) {
    private fun dp(v: Int) = TypedValue.applyDimension(TypedValue.COMPLEX_UNIT_DIP, v.toFloat(), activity.resources.displayMetrics).toInt()

    fun clear() = content.removeAllViews()

    fun title(text: String) = add(R.layout.item_section, text)

    fun note(text: CharSequence) = add(R.layout.item_note, text)

    fun body(text: CharSequence): TextView = add(R.layout.item_note, text).apply {
        setTextColor(activity.getColor(R.color.text))
        setTextSize(TypedValue.COMPLEX_UNIT_SP, 14f)
    }

    private fun add(layout: Int, text: CharSequence): TextView {
        val v = LayoutInflater.from(activity).inflate(layout, content, false) as TextView
        v.text = text
        content.addView(v)
        return v
    }

    /**
     * 표. 첫 열은 왼쪽 정렬·줄바꿈 허용, 나머지 열은 오른쪽 정렬.
     * [bold] 에 해당하는 행은 굵게.
     */
    fun table(headers: List<String>, rows: List<List<CharSequence>>, bold: (Int) -> Boolean = { false }) {
        val table = TableLayout(activity).apply {
            setColumnShrinkable(0, true)
            setColumnStretchable(0, true)
        }
        fun cell(text: CharSequence, col: Int, header: Boolean, strong: Boolean) = TextView(activity).apply {
            this.text = text
            setTextSize(TypedValue.COMPLEX_UNIT_SP, if (header) 12f else 13f)
            setTextColor(activity.getColor(if (header) R.color.sub else R.color.text))
            gravity = if (col == 0) Gravity.START else Gravity.END
            setPadding(if (col == 0) 0 else dp(10), dp(5), 0, dp(5))
            if (strong) setTypeface(typeface, Typeface.BOLD)
        }
        table.addView(TableRow(activity).apply {
            headers.forEachIndexed { c, h -> addView(cell(h, c, header = true, strong = false)) }
        })
        rows.forEachIndexed { r, row ->
            table.addView(TableRow(activity).apply {
                row.forEachIndexed { c, v -> addView(cell(v, c, header = false, strong = bold(r))) }
            })
        }
        content.addView(table)
    }

    fun colored(text: String, color: Int): CharSequence =
        SpannableString(text).apply { setSpan(ForegroundColorSpan(activity.getColor(color)), 0, length, Spanned.SPAN_EXCLUSIVE_EXCLUSIVE) }

    /** 양수 빨강, 음수 파랑. */
    fun signed(text: String, v: Double): CharSequence =
        colored(text, if (v > 0.0005) R.color.up else if (v < -0.0005) R.color.down else R.color.flat)

    fun bold(text: String): CharSequence =
        SpannableString(text).apply { setSpan(StyleSpan(Typeface.BOLD), 0, length, Spanned.SPAN_EXCLUSIVE_EXCLUSIVE) }
}

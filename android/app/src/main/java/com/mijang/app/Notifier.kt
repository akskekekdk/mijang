package com.mijang.app

import android.Manifest
import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.graphics.BitmapFactory
import android.os.Build
import android.text.SpannableStringBuilder
import android.text.Spanned
import android.text.style.ForegroundColorSpan
import androidx.core.app.NotificationCompat
import androidx.core.app.NotificationManagerCompat

object Notifier {
    private const val CHANNEL = "top20"
    private const val ID_BASE = 1
    private const val PAGE = 10
    private const val MAX_PAGES = 2

    fun createChannel(context: Context) {
        val channel = NotificationChannel(
            CHANNEL, context.getString(R.string.channel_name), NotificationManager.IMPORTANCE_DEFAULT
        ).apply {
            description = context.getString(R.string.channel_desc)
            setSound(null, null)
            enableVibration(false)
            setShowBadge(false)
            lockscreenVisibility = Notification.VISIBILITY_PUBLIC
        }
        context.getSystemService(NotificationManager::class.java).createNotificationChannel(channel)
    }

    /**
     * 알림 한 개에 BigText 는 13줄 정도까지만 보이므로, 스크린샷처럼 10종목 + 기준시각씩
     * 두 개로 나눠 띄운다 (1~10위가 위에 오도록 11~20위를 먼저 올린다).
     */
    fun show(context: Context, snapshot: Snapshot) {
        if (Build.VERSION.SDK_INT >= 33 &&
            context.checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED
        ) return

        val pages = snapshot.stocks.chunked(PAGE)
        val manager = NotificationManagerCompat.from(context)
        for (page in pages.indices.reversed()) {
            manager.notify(ID_BASE + page, build(context, snapshot, pages[page], page * PAGE + 1))
        }
        for (page in pages.size until MAX_PAGES) manager.cancel(ID_BASE + page)
    }

    private fun build(context: Context, snapshot: Snapshot, stocks: List<Stock>, firstRank: Int): Notification {
        val body = SpannableStringBuilder(Format.lines(context, stocks, firstRank)).append("\n\n")
        val start = body.length
        body.append(Format.asOf(snapshot.quotedAt))
        body.setSpan(ForegroundColorSpan(context.getColor(R.color.sub)), start, body.length, Spanned.SPAN_EXCLUSIVE_EXCLUSIVE)

        val lastRank = firstRank + stocks.size - 1
        val first = stocks.first()
        val collapsed = "$firstRank. ${first.name} ${Format.price(first.price)} ${Format.percent(first.change)} 외 ${stocks.size - 1}종목"

        val open = PendingIntent.getActivity(
            context, 0, Intent(context, MainActivity::class.java),
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )
        return NotificationCompat.Builder(context, CHANNEL)
            .setSmallIcon(R.drawable.ic_stat_mijang)
            .setLargeIcon(BitmapFactory.decodeResource(context.resources, R.drawable.ic_notif_large))
            .setContentTitle("${context.getString(R.string.title)} · $firstRank~${lastRank}위")
            .setContentText(collapsed)
            .setStyle(NotificationCompat.BigTextStyle().bigText(body))
            .setVisibility(NotificationCompat.VISIBILITY_PUBLIC)
            .setOnlyAlertOnce(true)
            .setSilent(true)
            .setShowWhen(false)
            .setSortKey("page$firstRank")
            .setContentIntent(open)
            .build()
    }
}

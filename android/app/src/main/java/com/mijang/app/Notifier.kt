package com.mijang.app

import android.Manifest
import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import android.widget.RemoteViews
import androidx.core.app.NotificationCompat
import androidx.core.app.NotificationManagerCompat

object Notifier {
    private const val CHANNEL = "top20"
    private const val ID = 1
    private const val OLD_SECOND_PAGE_ID = 2
    private const val COLLAPSED_ROWS = 3

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
     * 알림 한 개에 20종목 + 기준 시각을 모두 넣는다. 기본 템플릿(BigTextStyle)은 글자 크기를 못 바꾸고
     * 높이 제한 때문에 20줄이 잘리므로, 작은 글씨의 커스텀 레이아웃을 쓴다. 제목은 넣지 않는다.
     */
    fun show(context: Context, snapshot: Snapshot) {
        if (Build.VERSION.SDK_INT >= 33 &&
            context.checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED
        ) return

        val big = RemoteViews(context.packageName, R.layout.notif_big)
        addRows(context, big, snapshot.stocks)
        big.setTextViewText(R.id.footer, Format.asOf(snapshot.quotedAt))

        val small = RemoteViews(context.packageName, R.layout.notif_small)
        addRows(context, small, snapshot.stocks.take(COLLAPSED_ROWS))

        val open = PendingIntent.getActivity(
            context, 0, Intent(context, MainActivity::class.java),
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )
        val notification = NotificationCompat.Builder(context, CHANNEL)
            .setSmallIcon(R.drawable.ic_stat_mijang)
            .setStyle(NotificationCompat.DecoratedCustomViewStyle())
            .setCustomContentView(small)
            .setCustomBigContentView(big)
            .setVisibility(NotificationCompat.VISIBILITY_PUBLIC)
            .setOnlyAlertOnce(true)
            .setSilent(true)
            .setShowWhen(false)
            .setContentIntent(open)
            .build()
        val manager = NotificationManagerCompat.from(context)
        manager.cancel(OLD_SECOND_PAGE_ID) // 이전 버전의 11~20위 알림 정리
        manager.notify(ID, notification)
    }

    private fun addRows(context: Context, parent: RemoteViews, stocks: List<Stock>) {
        parent.removeAllViews(R.id.rows)
        Format.rows(context, stocks).forEach { line ->
            val row = RemoteViews(context.packageName, R.layout.notif_row)
            row.setTextViewText(R.id.row, line)
            parent.addView(R.id.rows, row)
        }
    }
}

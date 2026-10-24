// Real Qt/resource contract tests. Compile with the exact overlay resource collection.
#include "StreamStrikeBranding.hpp"
#include "StreamStrikeCapture.hpp"

#include <QApplication>
#include <QCryptographicHash>
#include <QFile>
#include <QElapsedTimer>
#include <QThread>
#include <QImage>
#include <QTemporaryDir>

#include <iostream>

static int failures = 0;
static void check(bool condition, const char *message)
{
	if (!condition) {
		std::cerr << "FAIL: " << message << '\n';
		++failures;
	}
}

int main(int argc, char **argv)
{
	QApplication app(argc, argv);
	if (app.arguments().contains(QStringLiteral("--wait-for-native-tray"))) {
		if (QGuiApplication::platformName() != QStringLiteral("xcb"))
			return 1;
		QElapsedTimer wait;
		wait.start();
		do {
			app.processEvents();
			if (QSystemTrayIcon::isSystemTrayAvailable())
				return 0;
			QThread::msleep(100);
		} while (wait.elapsed() < 10000);
		std::cerr << "Native system tray host did not become available\n";
		return 1;
	}
	QFile resource(":/res/images/streamstrike.png");
	check(resource.open(QIODevice::ReadOnly), "compiled master resource must be readable");
	const QByteArray original = resource.readAll();
	check(QCryptographicHash::hash(original, QCryptographicHash::Sha256).toHex() ==
		      "86acca5004fbe90a471230159b452d3eb4a3663db30dac5d26523f43f470d926",
	      "compiled master must be the existing published PNG without raster edits");
	const QImage master = QImage::fromData(original).convertToFormat(QImage::Format_ARGB32_Premultiplied);
	check(master.size() == QSize(1024, 1024), "master dimensions");
	check(master.pixelColor(0, 0).alpha() == 0, "master transparent corner");

	const QImage idle = StreamStrikeBranding::icon(StreamStrikeBranding::State::Idle)
				   .pixmap(1024, 1024)
				   .toImage()
				   .convertToFormat(QImage::Format_ARGB32_Premultiplied);
	const QImage active = StreamStrikeBranding::icon(StreamStrikeBranding::State::Active)
				     .pixmap(1024, 1024)
				     .toImage()
				     .convertToFormat(QImage::Format_ARGB32_Premultiplied);
	const QImage paused = StreamStrikeBranding::icon(StreamStrikeBranding::State::Paused)
				     .pixmap(1024, 1024)
				     .toImage()
				     .convertToFormat(QImage::Format_ARGB32_Premultiplied);
	check(idle == master, "idle icon is exactly the existing master pixels");
	check(active != idle && paused != idle && active != paused, "all three tray states differ");
	check(active.copy(0, 0, 700, 700) == master.copy(0, 0, 700, 700),
	      "active state preserves the principal geometric mark");
	check(paused.copy(0, 0, 700, 700) == master.copy(0, 0, 700, 700),
	      "paused state preserves the principal geometric mark");
	check(active.pixelColor(864, 864) != paused.pixelColor(864, 864), "status glyphs are distinct");
	check(active.pixelColor(831, 864).alpha() == 255 && paused.pixelColor(831, 864).alpha() == 0,
	      "pause bars remain distinct in native monochrome tray templates");
	for (int size : {16, 24, 32, 48, 64, 128, 256}) {
		const QImage a = StreamStrikeBranding::trayIcon(StreamStrikeBranding::State::Active)
					.pixmap(size, size)
					.toImage();
		const QImage p = StreamStrikeBranding::trayIcon(StreamStrikeBranding::State::Paused)
					.pixmap(size, size)
					.toImage();
		check(!a.isNull() && !p.isNull() && a != p, "small state icons remain readable and distinct");
	}

	// Removing the early disabled branch would create a timer or reject null arguments here.
	qunsetenv("STREAMSTRIKE_CAPTURE_DIR");
	check(!StreamStrikeCapture::schedule(nullptr, nullptr), "ordinary launch does not schedule capture");
	app.processEvents();

	std::cout << "StreamStrike Qt identity tests: " << (failures ? "FAIL" : "PASS") << '\n';
	return failures ? 1 : 0;
}

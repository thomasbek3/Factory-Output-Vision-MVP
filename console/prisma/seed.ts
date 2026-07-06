import { PrismaClient } from "@prisma/client";
import { PrismaBetterSqlite3 } from "@prisma/adapter-better-sqlite3";

const adapter = new PrismaBetterSqlite3({ url: "prisma/dev.db" });
const prisma = new PrismaClient({ adapter });

const workHours = {
  monday: { start: "07:00", end: "17:30" },
  tuesday: { start: "07:00", end: "17:30" },
  wednesday: { start: "07:00", end: "17:30" },
  thursday: { start: "07:00", end: "17:30" },
  friday: { start: "07:00", end: "17:30" },
};

async function main() {
  const now = new Date("2026-06-26T07:00:00-07:00");

  await prisma.laborConfig.upsert({
    where: { id: "default" },
    update: {
      work_hours: workHours,
      hourly_rate_usd: 22,
      workers_per_station: 1,
    },
    create: {
      id: "default",
      work_hours: workHours,
      hourly_rate_usd: 22,
      workers_per_station: 1,
    },
  });

  await prisma.camera.upsert({
    where: { id: "CAM-01" },
    update: {
      name: "Pallet A camera",
      rtsp_url: "rtsp://demo.local/cam-01",
      station_id: "pallet-a",
      status: "online",
      last_frame_at: now,
    },
    create: {
      id: "CAM-01",
      name: "Pallet A camera",
      rtsp_url: "rtsp://demo.local/cam-01",
      station_id: "pallet-a",
      status: "online",
      last_frame_at: now,
    },
  });

  await prisma.camera.upsert({
    where: { id: "CAM-02" },
    update: {
      name: "Gate line camera",
      rtsp_url: "rtsp://demo.local/cam-02",
      station_id: "gate-line",
      status: "online",
      last_frame_at: now,
    },
    create: {
      id: "CAM-02",
      name: "Gate line camera",
      rtsp_url: "rtsp://demo.local/cam-02",
      station_id: "gate-line",
      status: "online",
      last_frame_at: now,
    },
  });

  await prisma.station.upsert({
    where: { id: "pallet-a" },
    update: {
      name: "Pallet A",
      camera_id: "CAM-01",
      zone_polygon: [
        [0.18, 0.2],
        [0.88, 0.2],
        [0.88, 0.86],
        [0.18, 0.86],
      ],
      baseline_rate: 19,
      active: true,
    },
    create: {
      id: "pallet-a",
      name: "Pallet A",
      camera_id: "CAM-01",
      zone_polygon: [
        [0.18, 0.2],
        [0.88, 0.2],
        [0.88, 0.86],
        [0.18, 0.86],
      ],
      baseline_rate: 19,
      active: true,
    },
  });

  await prisma.station.upsert({
    where: { id: "gate-line" },
    update: {
      name: "Gate line",
      camera_id: "CAM-02",
      zone_polygon: [
        [0.12, 0.18],
        [0.9, 0.18],
        [0.9, 0.82],
        [0.12, 0.82],
      ],
      baseline_rate: 8,
      active: true,
    },
    create: {
      id: "gate-line",
      name: "Gate line",
      camera_id: "CAM-02",
      zone_polygon: [
        [0.12, 0.18],
        [0.9, 0.18],
        [0.9, 0.82],
        [0.12, 0.82],
      ],
      baseline_rate: 8,
      active: true,
    },
  });

  const jobs = [
    {
      id: "job-ramirez-fencing",
      client: "Ramirez Fencing",
      title: "400 wire panels",
      units_required: 400,
      quote_usd: 1000,
      cogs_usd: 500,
      labor_budget_usd: 300,
      deadline: new Date("2026-06-29T10:15:05-07:00"),
      station_ids: ["pallet-a"],
      notes: "Pitch demo active job.",
    },
    {
      id: "job-delgado-hvac",
      client: "Delgado HVAC",
      title: "600 brackets",
      units_required: 600,
      quote_usd: 1800,
      cogs_usd: 700,
      labor_budget_usd: 520,
      deadline: new Date("2026-06-30T12:16:44-07:00"),
      station_ids: ["gate-line"],
      notes: "Spec checkpoint seed job.",
    },
    {
      id: "job-alvarez-gates",
      client: "Alvarez Gates",
      title: "120 frame gates",
      units_required: 120,
      quote_usd: 2400,
      cogs_usd: 1150,
      labor_budget_usd: 800,
      deadline: new Date("2026-06-30T08:33:33-07:00"),
      station_ids: ["gate-line", "pallet-a"],
      notes: "Spec checkpoint seed job.",
    },
  ];

  for (const job of jobs) {
    await prisma.job.upsert({
      where: { id: job.id },
      update: {
        ...job,
        status: "active",
        created_at:
          job.id === "job-alvarez-gates"
            ? new Date("2026-06-25T07:00:00-07:00")
            : job.id === "job-ramirez-fencing"
              ? new Date("2026-06-26T07:47:49-07:00")
              : now,
        finished_at: null,
      },
      create: {
        ...job,
        status: "active",
        created_at:
          job.id === "job-alvarez-gates"
            ? new Date("2026-06-25T07:00:00-07:00")
            : job.id === "job-ramirez-fencing"
              ? new Date("2026-06-26T07:47:49-07:00")
              : now,
        finished_at: null,
      },
    });
  }
}

main()
  .then(async () => {
    await prisma.$disconnect();
  })
  .catch(async (error) => {
    console.error(error);
    await prisma.$disconnect();
    process.exit(1);
  });

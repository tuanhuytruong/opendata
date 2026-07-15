import { Dataset } from '../types';

export const defaultDatasets: Dataset[] = [
  {
    id: 'sales-growth',
    name: 'E-Commerce Revenue & Sales Growth',
    description: 'Monthly track of sales revenue, marketing investments, customer acquisitions, and average transaction values over a calendar year.',
    category: 'Finance & Sales',
    columns: ['Month', 'Revenue', 'MarketingSpend', 'Acquisitions', 'AverageOrderValue'],
    numericColumns: ['Revenue', 'MarketingSpend', 'Acquisitions', 'AverageOrderValue'],
    data: [
      { Month: 'January', Revenue: 45000, MarketingSpend: 8000, Acquisitions: 1200, AverageOrderValue: 75.0 },
      { Month: 'February', Revenue: 48000, MarketingSpend: 8500, Acquisitions: 1350, AverageOrderValue: 78.5 },
      { Month: 'March', Revenue: 52000, MarketingSpend: 9000, Acquisitions: 1500, AverageOrderValue: 80.0 },
      { Month: 'April', Revenue: 58000, MarketingSpend: 9500, Acquisitions: 1720, AverageOrderValue: 82.3 },
      { Month: 'May', Revenue: 64000, MarketingSpend: 11000, Acquisitions: 1980, AverageOrderValue: 84.1 },
      { Month: 'June', Revenue: 71000, MarketingSpend: 12000, Acquisitions: 2200, AverageOrderValue: 86.5 },
      { Month: 'July', Revenue: 68000, MarketingSpend: 11500, Acquisitions: 2050, AverageOrderValue: 85.0 },
      { Month: 'August', Revenue: 75000, MarketingSpend: 13000, Acquisitions: 2400, AverageOrderValue: 88.2 },
      { Month: 'September', Revenue: 82000, MarketingSpend: 14000, Acquisitions: 2750, AverageOrderValue: 90.0 },
      { Month: 'October', Revenue: 89000, MarketingSpend: 15500, Acquisitions: 3100, AverageOrderValue: 92.4 },
      { Month: 'November', Revenue: 105000, MarketingSpend: 18000, Acquisitions: 3800, AverageOrderValue: 95.8 },
      { Month: 'December', Revenue: 125000, MarketingSpend: 22000, Acquisitions: 4500, AverageOrderValue: 102.5 }
    ]
  },
  {
    id: 'web-performance',
    name: 'Website Daily Performance & Conversions',
    description: '30 days of web traffic, engagement indices, conversion percentages, and user sign-ups for a modern portal.',
    category: 'Marketing & Web',
    columns: ['Day', 'Visitors', 'BounceRate', 'Signups', 'ConversionRate'],
    numericColumns: ['Visitors', 'BounceRate', 'Signups', 'ConversionRate'],
    data: [
      { Day: 'Day 1', Visitors: 3200, BounceRate: 42.5, Signups: 120, ConversionRate: 3.75 },
      { Day: 'Day 2', Visitors: 3400, BounceRate: 41.2, Signups: 135, ConversionRate: 3.97 },
      { Day: 'Day 3', Visitors: 3100, BounceRate: 43.8, Signups: 115, ConversionRate: 3.71 },
      { Day: 'Day 4', Visitors: 2900, BounceRate: 45.0, Signups: 98, ConversionRate: 3.38 },
      { Day: 'Day 5', Visitors: 3500, BounceRate: 40.5, Signups: 142, ConversionRate: 4.06 },
      { Day: 'Day 6', Visitors: 3800, BounceRate: 38.9, Signups: 168, ConversionRate: 4.42 },
      { Day: 'Day 7', Visitors: 4200, BounceRate: 37.2, Signups: 195, ConversionRate: 4.64 },
      { Day: 'Day 8', Visitors: 4050, BounceRate: 38.1, Signups: 182, ConversionRate: 4.49 },
      { Day: 'Day 9', Visitors: 3900, BounceRate: 39.0, Signups: 170, ConversionRate: 4.36 },
      { Day: 'Day 10', Visitors: 3700, BounceRate: 40.2, Signups: 155, ConversionRate: 4.19 },
      { Day: 'Day 11', Visitors: 3550, BounceRate: 41.5, Signups: 140, ConversionRate: 3.94 },
      { Day: 'Day 12', Visitors: 3300, BounceRate: 42.8, Signups: 118, ConversionRate: 3.58 },
      { Day: 'Day 13', Visitors: 3800, BounceRate: 39.5, Signups: 162, ConversionRate: 4.26 },
      { Day: 'Day 14', Visitors: 4400, BounceRate: 36.8, Signups: 210, ConversionRate: 4.77 },
      { Day: 'Day 15', Visitors: 4600, BounceRate: 35.5, Signups: 232, ConversionRate: 5.04 },
      { Day: 'Day 16', Visitors: 4300, BounceRate: 37.0, Signups: 204, ConversionRate: 4.74 },
      { Day: 'Day 17', Visitors: 4150, BounceRate: 38.2, Signups: 188, ConversionRate: 4.53 },
      { Day: 'Day 18', Visitors: 3950, BounceRate: 39.6, Signups: 172, ConversionRate: 4.35 },
      { Day: 'Day 19', Visitors: 3800, BounceRate: 40.1, Signups: 160, ConversionRate: 4.21 },
      { Day: 'Day 20', Visitors: 4200, BounceRate: 37.9, Signups: 192, ConversionRate: 4.57 },
      { Day: 'Day 21', Visitors: 4800, BounceRate: 34.2, Signups: 254, ConversionRate: 5.29 },
      { Day: 'Day 22', Visitors: 5100, BounceRate: 33.0, Signups: 285, ConversionRate: 5.59 },
      { Day: 'Day 23', Visitors: 4950, BounceRate: 34.0, Signups: 268, ConversionRate: 5.41 },
      { Day: 'Day 24', Visitors: 4700, BounceRate: 35.5, Signups: 240, ConversionRate: 5.11 },
      { Day: 'Day 25', Visitors: 4450, BounceRate: 36.8, Signups: 218, ConversionRate: 4.90 },
      { Day: 'Day 26', Visitors: 4200, BounceRate: 38.0, Signups: 190, ConversionRate: 4.52 },
      { Day: 'Day 27', Visitors: 4600, BounceRate: 35.2, Signups: 230, ConversionRate: 5.00 },
      { Day: 'Day 28', Visitors: 5400, BounceRate: 31.8, Signups: 320, ConversionRate: 5.93 },
      { Day: 'Day 29', Visitors: 5800, BounceRate: 30.2, Signups: 362, ConversionRate: 6.24 },
      { Day: 'Day 30', Visitors: 6200, BounceRate: 28.5, Signups: 410, ConversionRate: 6.61 }
    ]
  },
  {
    id: 'saas-engagement',
    name: 'SaaS Customer Engagement & Retention',
    description: 'Weekly user session trends, customer churn rates, average time spent in-app, and feature usage scores.',
    category: 'SaaS Analytics',
    columns: ['Week', 'ActiveUsers', 'AvgSessionMinutes', 'ChurnRate', 'FeatureUsageScore'],
    numericColumns: ['ActiveUsers', 'AvgSessionMinutes', 'ChurnRate', 'FeatureUsageScore'],
    data: [
      { Week: 'W1', ActiveUsers: 1200, AvgSessionMinutes: 24.5, ChurnRate: 4.5, FeatureUsageScore: 68 },
      { Week: 'W2', ActiveUsers: 1250, AvgSessionMinutes: 25.2, ChurnRate: 4.2, FeatureUsageScore: 70 },
      { Week: 'W3', ActiveUsers: 1310, AvgSessionMinutes: 26.0, ChurnRate: 3.9, FeatureUsageScore: 71 },
      { Week: 'W4', ActiveUsers: 1280, AvgSessionMinutes: 24.8, ChurnRate: 4.1, FeatureUsageScore: 69 },
      { Week: 'W5', ActiveUsers: 1380, AvgSessionMinutes: 27.5, ChurnRate: 3.6, FeatureUsageScore: 74 },
      { Week: 'W6', ActiveUsers: 1450, AvgSessionMinutes: 28.1, ChurnRate: 3.2, FeatureUsageScore: 78 },
      { Week: 'W7', ActiveUsers: 1520, AvgSessionMinutes: 29.4, ChurnRate: 2.8, FeatureUsageScore: 82 },
      { Week: 'W8', ActiveUsers: 1490, AvgSessionMinutes: 28.8, ChurnRate: 3.0, FeatureUsageScore: 80 },
      { Week: 'W9', ActiveUsers: 1580, AvgSessionMinutes: 30.5, ChurnRate: 2.5, FeatureUsageScore: 85 },
      { Week: 'W10', ActiveUsers: 1720, AvgSessionMinutes: 32.2, ChurnRate: 2.1, FeatureUsageScore: 89 }
    ]
  },
  {
    id: 'solar-energy',
    name: 'Hourly Clean Energy Generation',
    description: 'Hourly solar array output (MWh), wind turbine output (MWh), grid load requirements, and generator efficiency indexes.',
    category: 'Energy & Environment',
    columns: ['Hour', 'SolarOutput', 'WindOutput', 'GridDemand', 'SystemEfficiency'],
    numericColumns: ['SolarOutput', 'WindOutput', 'GridDemand', 'SystemEfficiency'],
    data: [
      { Hour: '00:00', SolarOutput: 0.0, WindOutput: 45.2, GridDemand: 110.5, SystemEfficiency: 82.5 },
      { Hour: '02:00', SolarOutput: 0.0, WindOutput: 48.1, GridDemand: 98.2, SystemEfficiency: 84.1 },
      { Hour: '04:00', SolarOutput: 0.0, WindOutput: 44.5, GridDemand: 92.0, SystemEfficiency: 83.0 },
      { Hour: '06:00', SolarOutput: 5.2, WindOutput: 39.8, GridDemand: 105.4, SystemEfficiency: 85.6 },
      { Hour: '08:00', SolarOutput: 25.8, WindOutput: 35.0, GridDemand: 125.1, SystemEfficiency: 88.2 },
      { Hour: '10:00', SolarOutput: 68.4, WindOutput: 30.5, GridDemand: 138.6, SystemEfficiency: 91.4 },
      { Hour: '12:00', SolarOutput: 85.0, WindOutput: 28.2, GridDemand: 145.0, SystemEfficiency: 93.5 },
      { Hour: '14:00', SolarOutput: 79.5, WindOutput: 31.0, GridDemand: 142.3, SystemEfficiency: 92.1 },
      { Hour: '16:00', SolarOutput: 42.1, WindOutput: 38.6, GridDemand: 135.0, SystemEfficiency: 89.8 },
      { Hour: '18:00', SolarOutput: 12.4, WindOutput: 46.2, GridDemand: 140.2, SystemEfficiency: 86.4 },
      { Hour: '20:00', SolarOutput: 0.5, WindOutput: 52.8, GridDemand: 130.8, SystemEfficiency: 83.9 },
      { Hour: '22:00', SolarOutput: 0.0, WindOutput: 49.0, GridDemand: 120.0, SystemEfficiency: 82.8 }
    ]
  }
];

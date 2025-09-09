// News Intelligence System v3.1.0 - Sentiment Analysis Chart
// Interactive chart for sentiment analysis data

import React from 'react';
import { Box, Typography, Paper } from '@mui/material';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
  BarChart,
  Bar
} from 'recharts';

const SentimentChart = ({ data, type = 'line' }) => {
  const COLORS = {
    positive: '#4caf50',
    negative: '#f44336',
    neutral: '#ff9800'
  };

  const formatTooltip = (value, name) => {
    const labels = {
      positive: 'Positive',
      negative: 'Negative',
      neutral: 'Neutral'
    };
    return [value, labels[name] || name];
  };

  const renderLineChart = () => (
    <ResponsiveContainer width="100%" height={300}>
      <LineChart data={data}>
        <CartesianGrid strokeDasharray="3 3" />
        <XAxis dataKey="date" />
        <YAxis />
        <Tooltip formatter={formatTooltip} />
        <Legend />
        <Line 
          type="monotone" 
          dataKey="positive" 
          stroke={COLORS.positive} 
          strokeWidth={2}
          name="Positive"
        />
        <Line 
          type="monotone" 
          dataKey="negative" 
          stroke={COLORS.negative} 
          strokeWidth={2}
          name="Negative"
        />
        <Line 
          type="monotone" 
          dataKey="neutral" 
          stroke={COLORS.neutral} 
          strokeWidth={2}
          name="Neutral"
        />
      </LineChart>
    </ResponsiveContainer>
  );

  const renderPieChart = () => {
    const pieData = [
      { name: 'Positive', value: data.positive || 0, color: COLORS.positive },
      { name: 'Negative', value: data.negative || 0, color: COLORS.negative },
      { name: 'Neutral', value: data.neutral || 0, color: COLORS.neutral }
    ];

    return (
      <ResponsiveContainer width="100%" height={300}>
        <PieChart>
          <Pie
            data={pieData}
            cx="50%"
            cy="50%"
            labelLine={false}
            label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}
            outerRadius={80}
            fill="#8884d8"
            dataKey="value"
          >
            {pieData.map((entry, index) => (
              <Cell key={`cell-${index}`} fill={entry.color} />
            ))}
          </Pie>
          <Tooltip />
        </PieChart>
      </ResponsiveContainer>
    );
  };

  const renderBarChart = () => (
    <ResponsiveContainer width="100%" height={300}>
      <BarChart data={data}>
        <CartesianGrid strokeDasharray="3 3" />
        <XAxis dataKey="category" />
        <YAxis />
        <Tooltip formatter={formatTooltip} />
        <Legend />
        <Bar dataKey="positive" fill={COLORS.positive} name="Positive" />
        <Bar dataKey="negative" fill={COLORS.negative} name="Negative" />
        <Bar dataKey="neutral" fill={COLORS.neutral} name="Neutral" />
      </BarChart>
    </ResponsiveContainer>
  );

  const renderChart = () => {
    switch (type) {
      case 'pie':
        return renderPieChart();
      case 'bar':
        return renderBarChart();
      default:
        return renderLineChart();
    }
  };

  return (
    <Paper sx={{ p: 3, height: '100%' }}>
      <Typography variant="h6" gutterBottom>
        Sentiment Analysis
      </Typography>
      {renderChart()}
    </Paper>
  );
};

export default SentimentChart;


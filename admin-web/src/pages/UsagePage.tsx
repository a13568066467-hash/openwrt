import { Table } from 'antd';
import { useQuery } from '@tanstack/react-query';
import { adminApi, formatBytes } from '../api';
import PageShell from '../components/PageShell';

export default function UsagePage() {
  const { data, isLoading } = useQuery({
    queryKey: ['usage'],
    queryFn: () => adminApi.getUsage().then(r => r.data),
  });

  return (
    <PageShell title="用量报表">
      <Table
        loading={isLoading}
        dataSource={data}
        rowKey="id"
        pagination={{ pageSize: 10 }}
        columns={[
          { title: 'ID', dataIndex: 'id', width: 60 },
          { title: 'MAC', dataIndex: 'mac' },
          { title: '增量', dataIndex: 'delta_bytes', render: formatBytes },
          { title: '累计', dataIndex: 'total_bytes', render: formatBytes },
          { title: '会话', dataIndex: 'session_key', ellipsis: true },
          { title: '时间', dataIndex: 'recorded_at' },
        ]}
      />
    </PageShell>
  );
}

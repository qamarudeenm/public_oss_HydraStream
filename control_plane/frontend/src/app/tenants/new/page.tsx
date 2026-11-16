/**
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import * as z from 'zod';
import { createTenant } from '@/lib/api';
import { Check, ChevronRight, ChevronLeft, Loader2 } from 'lucide-react';

const schema = z.object({
  id: z.string().min(3, 'ID must be at least 3 characters'),
  name: z.string().min(3, 'Name must be at least 3 characters'),
  flink_version: z.string().min(1, 'Flink version is required'),
  dbt_version: z.string().min(1, 'dbt version is required'),
  kafka: z.object({
    bootstrap_servers: z.string().min(1, 'Bootstrap servers is required'),
    topic: z.string().min(1, 'Topic is required'),
    group_id: z.string().min(1, 'Group ID is required'),
  }),
  sink: z.object({
    jdbc_url: z.string().min(1, 'JDBC URL is required'),
    user: z.string().min(1, 'User is required'),
    password: z.string().min(1, 'Password is required'),
    summary_table: z.string().min(1, 'Summary table is required'),
    metrics_table: z.string().min(1, 'Metrics table is required'),
  }),
  environments: z.object({
    dev: z.object({
      hydra_runtime_id: z.string().min(1, 'Runtime ID is required'),
      dbt_environment_id: z.string().min(1, 'dbt environment ID is required'),
      dbt_project_id: z.string().min(1, 'dbt project ID is required'),
      dbt_service_token: z.string().min(1, 'Service token is required'),
    }),
    staging: z.object({
      hydra_runtime_id: z.string().min(1, 'Runtime ID is required'),
      dbt_environment_id: z.string().min(1, 'dbt environment ID is required'),
      dbt_project_id: z.string().min(1, 'dbt project ID is required'),
      dbt_service_token: z.string().min(1, 'Service token is required'),
    }),
    prod: z.object({
      hydra_runtime_id: z.string().min(1, 'Runtime ID is required'),
      dbt_environment_id: z.string().min(1, 'dbt environment ID is required'),
      dbt_project_id: z.string().min(1, 'dbt project ID is required'),
      dbt_service_token: z.string().min(1, 'Service token is required'),
    }),
  }),
});

type FormData = z.infer<typeof schema>;

export default function NewTenantWizard() {
  const [step, setStep] = useState(1);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const router = useRouter();

  const { register, handleSubmit, formState: { errors }, trigger } = useForm<FormData>({
    resolver: zodResolver(schema),
    defaultValues: {
      flink_version: '1.19.1',
      dbt_version: '1.7.0',
      kafka: {
        bootstrap_servers: 'kafka:29092',
        topic: 'clickstream',
        group_id: 'clickstream-consumer-group',
      },
      sink: {
        jdbc_url: 'jdbc:mysql://host.docker.internal:9004/clickstream',
        user: 'flink_user',
        password: '12345',
        summary_table: 'clickstream_summary',
        metrics_table: 'transformed_clickstream_metrics',
      },
      environments: {
        dev: {
          hydra_runtime_id: 'runtime-dev',
          dbt_environment_id: 'dbt-dev',
          dbt_project_id: 'project-main',
          dbt_service_token: '',
        },
        staging: {
          hydra_runtime_id: 'runtime-staging',
          dbt_environment_id: 'dbt-staging',
          dbt_project_id: 'project-main',
          dbt_service_token: '',
        },
        prod: {
          hydra_runtime_id: 'runtime-prod',
          dbt_environment_id: 'dbt-prod',
          dbt_project_id: 'project-main',
          dbt_service_token: '',
        },
      },
    }
  });

  const nextStep = async () => {
    let fields: string[] = [];
    if (step === 1) fields = ['id', 'name', 'flink_version', 'dbt_version'];
    if (step === 2) fields = ['kafka.bootstrap_servers', 'kafka.topic', 'kafka.group_id'];
    if (step === 3) fields = ['sink.jdbc_url', 'sink.user', 'sink.password', 'sink.summary_table', 'sink.metrics_table'];
    
    // @ts-expect-error - trigger expects specific paths but we're passing dynamic strings
    const isValid = await trigger(fields);
    if (isValid) setStep(step + 1);
  };

  const prevStep = () => setStep(step - 1);

  const onSubmit = async (data: FormData) => {
    setIsSubmitting(true);
    try {
      await createTenant(data);
      router.push('/');
    } catch (error) {
      console.error('Failed to create tenant', error);
      alert('Failed to create tenant. Please try again.');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div style={{ maxWidth: '800px', margin: '0 auto' }}>
      <h1 className="title">Create New Tenant</h1>
      <p className="subtitle">Configure your streaming pipeline infrastructure.</p>

      {/* Progress Bar */}
      <div style={{ display: 'flex', gap: '1rem', marginBottom: '3rem' }}>
        {[1, 2, 3, 4].map((s) => (
          <div key={s} style={{ flex: 1 }}>
            <div style={{ 
              height: '4px', 
              backgroundColor: s <= step ? 'var(--primary)' : 'var(--gray-200)',
              borderRadius: '2px',
              marginBottom: '0.5rem'
            }} />
            <span style={{ fontSize: '0.75rem', fontWeight: 600, color: s <= step ? 'var(--primary)' : 'var(--gray-300)' }}>
              STEP {s}: {s === 1 ? 'General' : s === 2 ? 'Kafka Source' : s === 3 ? 'JDBC Sink' : 'Env Mapping'}
            </span>
          </div>
        ))}
      </div>

      <div className="card">
        <form onSubmit={handleSubmit(onSubmit)}>
          {step === 1 && (
            <div>
              <h2 style={{ marginBottom: '1.5rem', fontSize: '1.25rem' }}>General Configuration</h2>
              <div className="form-group">
                <label htmlFor="id">Tenant ID (unique identifier)</label>
                <input id="id" {...register('id')} placeholder="e.g. acme-corp" />
                {errors.id && <p className="error-text">{errors.id.message}</p>}
              </div>
              <div className="form-group">
                <label htmlFor="name">Display Name</label>
                <input id="name" {...register('name')} placeholder="e.g. Acme Corporation" />
                {errors.name && <p className="error-text">{errors.name.message}</p>}
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
                <div className="form-group">
                  <label htmlFor="flink_version">Flink Version</label>
                  <select id="flink_version" {...register('flink_version')}>
                    <option value="1.19.1">1.19.1</option>
                    <option value="1.18.1">1.18.1</option>
                    <option value="2.0.0">2.0.0 (Beta)</option>
                  </select>
                </div>
                <div className="form-group">
                  <label htmlFor="dbt_version">dbt Version</label>
                  <select id="dbt_version" {...register('dbt_version')}>
                    <option value="1.7.0">1.7.0</option>
                    <option value="1.8.0">1.8.0</option>
                  </select>
                </div>
              </div>
            </div>
          )}

          {step === 2 && (
            <div>
              <h2 style={{ marginBottom: '1.5rem', fontSize: '1.25rem' }}>Kafka Source Settings</h2>
              <div className="form-group">
                <label htmlFor="kafka.bootstrap_servers">Bootstrap Servers</label>
                <input id="kafka.bootstrap_servers" {...register('kafka.bootstrap_servers')} placeholder="localhost:9092" />
                {errors.kafka?.bootstrap_servers && <p className="error-text">{errors.kafka.bootstrap_servers.message}</p>}
              </div>
              <div className="form-group">
                <label htmlFor="kafka.topic">Kafka Topic</label>
                <input id="kafka.topic" {...register('kafka.topic')} placeholder="clickstream" />
                {errors.kafka?.topic && <p className="error-text">{errors.kafka.topic.message}</p>}
              </div>
              <div className="form-group">
                <label htmlFor="kafka.group_id">Consumer Group ID</label>
                <input id="kafka.group_id" {...register('kafka.group_id')} placeholder="my-group" />
                {errors.kafka?.group_id && <p className="error-text">{errors.kafka.group_id.message}</p>}
              </div>
            </div>
          )}

          {step === 3 && (
            <div>
              <h2 style={{ marginBottom: '1.5rem', fontSize: '1.25rem' }}>Destination (JDBC Sink) Settings</h2>
              <div className="form-group">
                <label htmlFor="sink.jdbc_url">JDBC Connection URL</label>
                <input id="sink.jdbc_url" {...register('sink.jdbc_url')} placeholder="jdbc:mysql://host:port/db" />
                {errors.sink?.jdbc_url && <p className="error-text">{errors.sink.jdbc_url.message}</p>}
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
                <div className="form-group">
                  <label htmlFor="sink.user">Username</label>
                  <input id="sink.user" {...register('sink.user')} />
                  {errors.sink?.user && <p className="error-text">{errors.sink.user.message}</p>}
                </div>
                <div className="form-group">
                  <label htmlFor="sink.password">Password</label>
                  <input id="sink.password" type="password" {...register('sink.password')} />
                  {errors.sink?.password && <p className="error-text">{errors.sink.password.message}</p>}
                </div>
              </div>
              <div className="form-group">
                <label htmlFor="sink.summary_table">Summary Table Name</label>
                <input id="sink.summary_table" {...register('sink.summary_table')} />
                {errors.sink?.summary_table && <p className="error-text">{errors.sink.summary_table.message}</p>}
              </div>
              <div className="form-group">
                <label htmlFor="sink.metrics_table">Metrics Table Name</label>
                <input id="sink.metrics_table" {...register('sink.metrics_table')} />
                {errors.sink?.metrics_table && <p className="error-text">{errors.sink.metrics_table.message}</p>}
              </div>
            </div>
          )}

          {step === 4 && (
            <div>
              <h2 style={{ marginBottom: '1.5rem', fontSize: '1.25rem' }}>Environment Runtime Mapping</h2>
              {(['dev', 'staging', 'prod'] as const).map((env) => (
                <div key={env} style={{ marginBottom: '1.25rem', padding: '1rem', border: '1px solid var(--gray-200)', borderRadius: '0.5rem' }}>
                  <h3 style={{ marginBottom: '1rem', textTransform: 'uppercase', fontSize: '0.875rem' }}>{env}</h3>
                  <div className="form-group">
                    <label htmlFor={`environments.${env}.hydra_runtime_id`}>Hydra Runtime ID</label>
                    <input id={`environments.${env}.hydra_runtime_id`} {...register(`environments.${env}.hydra_runtime_id`)} />
                    {errors.environments?.[env]?.hydra_runtime_id && <p className="error-text">{errors.environments[env]?.hydra_runtime_id?.message}</p>}
                  </div>
                  <div className="form-group">
                    <label htmlFor={`environments.${env}.dbt_environment_id`}>dbt Environment ID</label>
                    <input id={`environments.${env}.dbt_environment_id`} {...register(`environments.${env}.dbt_environment_id`)} />
                    {errors.environments?.[env]?.dbt_environment_id && <p className="error-text">{errors.environments[env]?.dbt_environment_id?.message}</p>}
                  </div>
                  <div className="form-group">
                    <label htmlFor={`environments.${env}.dbt_project_id`}>dbt Project ID</label>
                    <input id={`environments.${env}.dbt_project_id`} {...register(`environments.${env}.dbt_project_id`)} />
                    {errors.environments?.[env]?.dbt_project_id && <p className="error-text">{errors.environments[env]?.dbt_project_id?.message}</p>}
                  </div>
                  <div className="form-group">
                    <label htmlFor={`environments.${env}.dbt_service_token`}>dbt Service Token</label>
                    <input id={`environments.${env}.dbt_service_token`} type="password" {...register(`environments.${env}.dbt_service_token`)} />
                    {errors.environments?.[env]?.dbt_service_token && <p className="error-text">{errors.environments[env]?.dbt_service_token?.message}</p>}
                  </div>
                </div>
              ))}
            </div>
          )}

          <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: '2.5rem', paddingTop: '1.5rem', borderTop: '1px solid var(--gray-200)' }}>
            {step > 1 ? (
              <button type="button" onClick={prevStep} className="btn" style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', backgroundColor: 'var(--gray-100)' }}>
                <ChevronLeft size={18} />
                Back
              </button>
            ) : (
              <div />
            )}

            {step < 4 ? (
              <button type="button" onClick={nextStep} className="btn btn-primary" style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                Next Step
                <ChevronRight size={18} />
              </button>
            ) : (
              <button type="submit" disabled={isSubmitting} className="btn btn-primary" style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                {isSubmitting ? <Loader2 className="animate-spin" size={18} /> : <Check size={18} />}
                {isSubmitting ? 'Provisioning...' : 'Deploy Pipeline'}
              </button>
            )}
          </div>
        </form>
      </div>
    </div>
  );
}
